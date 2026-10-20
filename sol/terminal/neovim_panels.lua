-- Shared popup lifecycle, search results and the printed-source panel.
return function(reader)
  local api = vim.api
  local data = reader.view.data
  local source_rows = reader.view.source_rows
  local window = reader.view.window
  local source_point = reader.view.source_point
  local native_cursor = reader.view.native_cursor
  local capture = reader.view.capture
  local set_exact_cursor = reader.view.set_exact_cursor
  local normal_escape = reader.view.normal_escape
  local restore = reader.view.restore
  local function request(...) return reader.requests.request(...) end
  local panels = {context_open = false}
  -- The narrowest panel worth putting beside the page, and the widest.
  local SIDE_MINIMUM, SIDE_MAXIMUM = 34, 64
  local panel_namespace = api.nvim_create_namespace('SOLPanelText')
  local function close_popup()
    local closing, packet = panels.window, panels.return_packet
    panels.window, panels.context_open, panels.return_packet = nil, false, nil
    if closing and api.nvim_win_is_valid(closing) then api.nvim_win_close(closing, true) end
    reader.view.set_side(0)
    if api.nvim_win_is_valid(window) then api.nvim_set_current_win(window) end
    if packet then restore(packet) end
  end
  -- Where a panel goes beside the page, moving the page left to make room;
  -- nil when the reader's columns are too narrow, and the panel goes over it.
  local function side_config()
    local columns = reader.view.reader_columns()
    local page = math.max(1, math.min(data.width, columns - 4))
    local room = columns - page - 6
    if room < SIDE_MINIMUM then return nil end
    local width = math.min(SIDE_MAXIMUM, room)
    reader.view.set_side(width + 4)
    local placed = api.nvim_win_get_config(window)
    return { relative = "editor", row = placed.row, col = placed.col + placed.width + 2, width = width,
      height = math.max(1, placed.height - 2) }
  end
  -- Beside the page when there is room, else over the page as before.
  -- marks: {line, group[, first, last]} in bytes. hanging: wrapped lines
  -- continue under this column (a key/description table).
  local function show_lines(lines, return_packet, marks, hanging)
    return_packet = return_packet or panels.return_packet
    close_popup()
    if vim.fn.mode(1) ~= 'n' then normal_escape() end
    local panel = api.nvim_create_buf(false, true)
    api.nvim_buf_set_lines(panel, 0, -1, false, lines)
    for _, mark in ipairs(marks or {}) do
      local text = lines[mark[1]] or ''
      api.nvim_buf_set_extmark(panel, panel_namespace, mark[1] - 1, mark[3] or 0,
        { end_col = math.min(#text, mark[4] or #text), hl_group = mark[2] })
    end
    vim.bo[panel].modifiable, vim.bo[panel].readonly, vim.bo[panel].bufhidden = false, true, "wipe"
    local config = side_config()
    if not config then
      local columns = reader.view.reader_columns()
      local width, height = math.max(1, math.min(data.width, columns - 6)), math.max(1, vim.o.lines - 8)
      config = { relative = "editor", row = 3, col = math.max(0, math.floor((columns - width) / 2)), width = width,
        height = math.min(height, math.max(1, #lines)) }
    end
    config.style, config.border, config.zindex = "minimal", "single", 50
    panels.window = api.nvim_open_win(panel, true, config)
    vim.wo[panels.window].wrap, vim.wo[panels.window].linebreak = true, true
    if hanging then
      vim.wo[panels.window].breakindent, vim.wo[panels.window].breakindentopt = true, 'shift:' .. hanging
    end
    vim.wo[panels.window].winhighlight = "NormalFloat:SOLPanel,FloatBorder:SOLPanelBorder"
    panels.return_packet = return_packet
    local opened = panels.window
    api.nvim_create_autocmd('WinClosed', {pattern = tostring(opened), once = true, callback = function()
      if panels.window == opened then close_popup() end
    end})
    for _, key in ipairs({ "<Esc>", "q", "c" }) do
      vim.keymap.set("n", key, close_popup, { buffer = panel, silent = true })
    end
    vim.keymap.set("n", "j", "gj", { buffer = panel, silent = true })
    vim.keymap.set("n", "k", "gk", { buffer = panel, silent = true })
  end
  local function current_packet()
    if panels.return_packet then return vim.deepcopy(panels.return_packet) end
    local cursor = native_cursor()
    if vim.fn.mode(1) == "n" and not source_rows[cursor.row] then
      local nearest, distance
      for row, item in pairs(source_rows) do
        local delta = math.abs(row - cursor.row)
        if not distance or delta < distance or (delta == distance and row < nearest.row) then
          nearest, distance = item, delta
        end
      end
      set_exact_cursor(source_point(nearest.id, cursor.row > nearest.row and nearest.finish or nearest.start))
    end
    return capture()
  end
  local show_search, show_source
  show_search = function(result)
    local lines = {'Search: ' .. result.query, 'Whole book, literal and case-insensitive. ' .. result.total .. ' matches in ' .. #result.rows .. ' passages.', ''}
    local rows = {}
    for _, item in ipairs(result.rows) do
      lines[#lines + 1] = item.number .. '. ' .. item.label
      rows[#lines] = item.number
      lines[#lines + 1] = '   ' .. item.snippet
      rows[#lines] = item.number
      lines[#lines + 1] = ''
    end
    if #result.rows == 0 then lines[#lines + 1] = 'No matching passages.' end
    lines[#lines + 1] = 'Enter reads a result; Esc returns unchanged. Ctrl-N/P visits matches.'
    show_lines(lines)
    local panel = api.nvim_get_current_buf()
    if #result.rows > 0 then api.nvim_win_set_cursor(panels.window, {4, 0}) end
    vim.keymap.set('n', '<CR>', function()
      local number = rows[api.nvim_win_get_cursor(panels.window)[1]]
      if not number then return end
      close_popup(); request('search_open', {result = number})
    end, {buffer = panel, silent = true})
  end
  -- The printed page is the authority for formulas the typed text cannot carry.
  -- Python renders it from the verified PDF; a separate viewer shows it, so this
  -- works in any terminal and the reading position never moves.
  show_source = function(result)
    local page = result.pages[result.shown]
    local lines = { 'Source: ' .. result.title, '',
      (result.cropped and 'Recorded region of PDF page ' or 'Whole PDF page ') .. page.pdf_page ..
        ' (printed page ' .. page.printed_page .. '), ' .. result.shown .. ' of ' .. #result.pages ..
        (result.cropped and '' or '; no region was recorded'),
      'Transcription: ' .. result.status }
    if result.note ~= '' then lines[#lines + 1] = result.note end
    lines[#lines + 1] = ''
    if result.viewer ~= vim.NIL then
      lines[#lines + 1] = 'Opened in ' .. result.viewer .. '. Rendered from the verified source PDF.'
    else
      lines[#lines + 1] = 'No graphical image viewer is available. Open this file yourself,'
      lines[#lines + 1] = 'or set SOL_IMAGE_VIEWER to a viewer command:'
    end
    lines[#lines + 1] = result.image
    if #result.pages > 1 then
      lines[#lines + 1] = ''
      for _, row in ipairs(result.pages) do
        lines[#lines + 1] = row.number .. '. PDF page ' .. row.pdf_page .. ', printed page ' .. row.printed_page ..
          (row.region and '' or ' (whole page)') .. (row.number == result.shown and '  [shown]' or '')
      end
    end
    lines[#lines + 1] = ''
    lines[#lines + 1] = (#result.pages > 1 and 'A page number shows that page. ' or '') .. 'Esc returns to reading.'
    show_lines(lines)
    local panel = api.nvim_get_current_buf()
    for _, row in ipairs(result.pages) do
      if row.number <= 9 then
        local number = row.number
        vim.keymap.set('n', tostring(number), function() request('source_preview', {page = number}) end,
          {buffer = panel, silent = true})
      end
    end
  end
  local function source()
    request('source_preview', {page = 1})
  end

  panels.close_popup, panels.show_lines, panels.current_packet = close_popup, show_lines, current_packet
  panels.side_config = side_config
  panels.show_search, panels.show_source = show_search, show_source
  panels.source = source
  return panels
end
