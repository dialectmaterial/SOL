-- Canonical book-note panels, bounded nested links and panel backtracking.
return function(reader)
  local api = vim.api
  local fail = reader.text.fail
  local integer = reader.text.integer
  local boundaries = reader.text.boundaries
  local slice = reader.text.slice
  local valid_styles = reader.text.valid_styles
  local valid_strings = reader.text.valid_strings
  local buffer = reader.view.buffer
  local window = reader.view.window
  local semantic_group = reader.view.semantic_group
  local superscript = reader.view.superscript
  local close_popup = reader.panels.close_popup
  local show_lines = reader.panels.show_lines
  local panels = reader.panels
  local request = reader.requests.request
  -- Book notes are disposable reading panels. Their canonical paragraphs keep
  -- independent IDs and codepoint spans; no panel position becomes a book visit.
  local function context(...) return reader.context(...) end
  local show_footnote
  local footnote_session
  local footnote_namespace = api.nvim_create_namespace('sol-footnote')
  local function open_footnote(trail, origin)
    local from = panels.window
    request('footnote_open', {trail = trail}, function(result)
      -- Closing the panel while Python works cancels the presentation, not a save.
      if from and api.nvim_win_is_valid(from) then show_footnote(result.footnote, origin) end
    end, origin)
  end
  local function attribution_line(attribution)
    if type(attribution) ~= 'table' then fail('invalid footnote attribution') end
    local values = {}
    for _, key in ipairs({'role', 'status', 'author'}) do
      local value = attribution[key]
      if type(value) == 'string' and value ~= '' then boundaries(value); values[#values + 1] = value end
    end
    return table.concat(values, ' · ')
  end
  show_footnote = function(note, origin, returning)
    if type(note) ~= 'table' or type(note.id) ~= 'string' or type(note.label) ~= 'string'
      or type(note.paragraphs) ~= 'table' or #note.paragraphs < 1 or #note.paragraphs > 64
      or type(note.links) ~= 'table' or #note.links > 128 or type(note.trail) ~= 'table'
      or #note.trail < 1 or #note.trail > 8 or note.trail[#note.trail] ~= note.id then
      fail('invalid bounded footnote view')
    end
    boundaries(note.label); valid_strings(note.warnings)
    local lines, warning_lines, body_rows, link_rows = {}, {}, {}, {}
    local function add(text)
      for _, line in ipairs(vim.split(text, '\n', {plain = true})) do lines[#lines + 1] = line end
    end
    local function warnings(items)
      valid_strings(items)
      for _, warning in ipairs(items) do
        add('Warning: ' .. warning); warning_lines[#warning_lines + 1] = #lines
      end
    end
    add('Book footnote [' .. note.label .. ']')
    add(attribution_line(note.attribution)); warnings(note.warnings); add('')
    for _, part in ipairs(note.paragraphs) do
      if type(part.id) ~= 'string' then fail('invalid footnote paragraph identity') end
      local length = #boundaries(part.plain_text) - 1
      valid_styles(part.styles, length)
      if not vim.deep_equal(part.attribution, note.attribution) then add(attribution_line(part.attribution)) end
      warnings(part.warnings)
      body_rows[#body_rows + 1] = {part = part, first = #lines + 1}
      add(part.plain_text); add('')
      if type(part.callouts) ~= 'table' then fail('invalid footnote callouts') end
      for _, mark in ipairs(part.callouts) do
        if not integer(mark.offset) or mark.offset < 0 or mark.offset > length
          or type(mark.label) ~= 'string' then fail('invalid footnote callout') end
        boundaries(mark.label)
      end
    end
    if #note.links > 0 then
      add('Further book footnotes · Enter opens the link under the cursor')
      for _, link in ipairs(note.links) do
        if type(link.id) ~= 'string' or type(link.label) ~= 'string' or type(link.refusal) ~= 'string' then
          fail('invalid footnote link')
        end
        boundaries(link.label); boundaries(link.refusal)
        add('[' .. link.label .. ']' .. (link.refusal ~= '' and (' · ' .. link.refusal) or ''))
        link_rows[#lines] = link
      end
      add('')
    end
    add('Backspace: back · Esc/q: reading')
    local state = footnote_session
    if not returning then
      if #note.trail == 1 or not state then
        state = {origin = origin, frames = {}, context_cursor = api.nvim_win_get_cursor(panels.window),
          context_view = vim.fn.winsaveview()}
      else
        local previous = state.frames[#state.frames]
        previous.cursor, previous.view = api.nvim_win_get_cursor(panels.window), vim.fn.winsaveview()
      end
      state.frames[#state.frames + 1] = {note = note}
    end
    show_lines(lines, origin)
    footnote_session = state
    local panel = api.nvim_get_current_buf()
    api.nvim_buf_set_extmark(panel, footnote_namespace, 0, 0,
      {end_row = 0, end_col = #lines[1], hl_group = 'SOLSourceHeading'})
    for _, row in ipairs(warning_lines) do
      api.nvim_buf_set_extmark(panel, footnote_namespace, row - 1, 0,
        {end_row = row - 1, end_col = #lines[row], hl_group = 'SOLSourceWarning'})
    end
    for _, body in ipairs(body_rows) do
      local function location(offset)
        local prefix = slice(body.part.plain_text, 0, offset)
        local _, newlines = prefix:gsub('\n', '')
        return body.first + newlines - 1, #(prefix:match('[^\n]*$'))
      end
      for _, span in ipairs(body.part.styles) do
        local row, byte = location(span.start)
        local last_row, last_byte = location(span['end'])
        api.nvim_buf_set_extmark(panel, footnote_namespace, row, byte,
          {end_row = last_row, end_col = last_byte, hl_group = semantic_group(span.styles)})
      end
      for _, callout in ipairs(body.part.callouts) do
        local row, byte = location(callout.offset)
        local mark = callout.label:match('^%d+$') and callout.label:gsub('%d', superscript) or '[' .. callout.label .. ']'
        api.nvim_buf_set_extmark(panel, footnote_namespace, row, byte,
          {virt_text = {{mark, 'NonText'}}, virt_text_pos = 'inline', right_gravity = false})
      end
    end
    local function finish() footnote_session = nil; close_popup() end
    for _, key in ipairs({'<Esc>', 'q', 'c'}) do
      vim.keymap.set('n', key, finish, {buffer = panel, silent = true})
    end
    vim.keymap.set('n', '<CR>', function()
      local link = link_rows[api.nvim_win_get_cursor(panels.window)[1]]
      if not link then vim.notify('Move onto a further footnote link first.', vim.log.levels.INFO); return end
      if link.refusal ~= '' then vim.notify(link.refusal, vim.log.levels.WARN); return end
      local trail = vim.deepcopy(note.trail); trail[#trail + 1] = link.id
      open_footnote(trail, origin)
    end, {buffer = panel, silent = true})
    vim.keymap.set('n', '<BS>', function()
      table.remove(state.frames)
      local previous = state.frames[#state.frames]
      if previous then
        show_footnote(previous.note, origin, true)
        api.nvim_win_set_cursor(panels.window, previous.cursor); vim.fn.winrestview(previous.view)
      else
        footnote_session = nil; context(origin)
        api.nvim_win_set_cursor(panels.window, state.context_cursor); vim.fn.winrestview(state.context_view)
      end
    end, {buffer = panel, silent = true})
  end

  return {open = open_footnote, show = show_footnote, attribution_line = attribution_line}
end
