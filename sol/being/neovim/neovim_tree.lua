-- One outline, one selection. Display paths never become source identities.
local M, api = {}, vim.api
function M.open(structure, callbacks)
  local nodes = {}
  for _, node in ipairs(structure.nodes) do nodes[node.key] = node end
  local current = assert(nodes[structure.current], 'current source branch is missing')
  local root = structure.root or (nodes[structure.doctrine] and structure.doctrine or '/')
  local selected, expanded, rows = current.key, {}, {}
  local function expand(key, depth)
    if depth <= 0 then return end
    expanded[key] = true
    for _, child in ipairs(nodes[key].children) do expand(child, depth - 1) end
  end
  expand(root, structure.depth or 2)
  -- Reveal the current ancestry even when it is deeper than the initial depth.
  local at = current.key
  while at ~= root and nodes[at].parent do
    at = nodes[at].parent; expanded[at] = true
  end
  local buffer = api.nvim_create_buf(false, true)
  vim.bo[buffer].buftype, vim.bo[buffer].bufhidden = 'nofile', 'wipe'
  local window
  local namespace = api.nvim_create_namespace('SOLOutline')
  local WIDEST = 84
  local function width()
    -- Beside ESSENCE, the outline keeps to the reader's columns.
    local essence = rawget(_G, 'SOLEssence')
    local columns = vim.o.columns - (essence and essence.reserved and essence.reserved() or 0)
    return math.max(1, math.min(WIDEST, columns - 4)), columns
  end
  -- Rows the outline currently shows: the panel is no taller than its content.
  local shown = 1
  local function config()
    local inner, columns = width()
    return {relative = 'editor', row = 1, col = math.max(1, math.floor((columns - inner) / 2) - 1), width = inner,
      height = math.max(1, math.min(vim.o.lines - 4, shown)), style = 'minimal', border = 'rounded', zindex = 60,
      title = ' Outline ', title_pos = 'center'}
  end
  local function draw()
    local inner = width()
    local hint = 'j/k move · h/l fold · Enter read · Esc back'
    if vim.fn.strdisplaywidth(hint) > inner then hint = 'j/k · h/l · Enter read · Esc back' end
    local lines, marks = {hint, ''}, {{1, 'NonText'}}
    local cursor_row
    rows = {}
    local function visit(key, level)
      local node = nodes[key]
      local fold = #node.children == 0 and '  ' or expanded[key] and '▾ ' or '▸ '
      local here = key == current.key and '● ' or '  '
      local page = node.page and ('p. ' .. node.page) or ''
      -- The page sits at the right edge; a long title gives way with an ellipsis.
      local room = inner - vim.fn.strdisplaywidth(page) - 2
      -- Deep branches still leave room for the fold/current marks and title.
      local indent = string.rep('  ', math.min(level, math.max(0, math.floor((room - 8) / 2))))
      local label = indent .. fold .. here .. node.title:gsub('%s+', ' ')
      if vim.fn.strdisplaywidth(label) > room then
        local shortened = ''
        for _, char in ipairs(vim.fn.split(label, '\\zs')) do
          if vim.fn.strdisplaywidth(shortened .. char .. '…') > room then break end
          shortened = shortened .. char
        end
        label = shortened .. '…'
      end
      local line = label .. string.rep(' ', math.max(1, inner - vim.fn.strdisplaywidth(label) - vim.fn.strdisplaywidth(page))) .. page
      lines[#lines + 1] = line
      rows[#lines] = key
      local glyphs = #(indent .. fold)
      if fold ~= '  ' then marks[#marks + 1] = {#lines, 'NonText', #indent, glyphs} end
      if key == current.key then marks[#marks + 1] = {#lines, 'SOLSourceHeading', glyphs, #label} end
      if page ~= '' then marks[#marks + 1] = {#lines, 'NonText', #line - #page, #line} end
      if key == selected then cursor_row = #lines end
      if expanded[key] then for _, child in ipairs(node.children) do visit(child, level + 1) end end
    end
    visit(root, 0)
    vim.bo[buffer].readonly, vim.bo[buffer].modifiable = false, true
    api.nvim_buf_set_lines(buffer, 0, -1, false, lines)
    vim.bo[buffer].modifiable, vim.bo[buffer].readonly = false, true
    shown = #lines
    if window and api.nvim_win_is_valid(window) then api.nvim_win_set_config(window, config()) end
    api.nvim_buf_clear_namespace(buffer, namespace, 0, -1)
    for _, mark in ipairs(marks) do
      api.nvim_buf_set_extmark(buffer, namespace, mark[1] - 1, mark[3] or 0,
        {end_col = math.min(#lines[mark[1]], mark[4] or #lines[mark[1]]), hl_group = mark[2]})
    end
    if window and api.nvim_win_is_valid(window) then
      api.nvim_win_set_cursor(window, {assert(cursor_row, 'outline selection is not visible'), 0})
    end
  end
  draw()
  window = api.nvim_open_win(buffer, true, config())
  vim.wo[window].wrap, vim.wo[window].cursorline, vim.wo[window].scrolloff = false, true, 2
  vim.wo[window].winhighlight = 'NormalFloat:SOLPanel,FloatBorder:SOLPanelBorder'
  draw()
  local function dispose()
    if window and api.nvim_win_is_valid(window) then api.nvim_win_close(window, true) end
    if api.nvim_buf_is_valid(buffer) then api.nvim_buf_delete(buffer, {force = true}) end
  end
  local function bind(key, fn)
    vim.keymap.set('n', key, function() fn(); draw() end, {buffer = buffer, silent = true})
  end
  local function move(delta)
    local row = api.nvim_win_get_cursor(window)[1] + delta
    if rows[row] then selected = rows[row] end
  end
  bind('j', function() move(1) end)
  bind('k', function() move(-1) end)
  bind('<Down>', function() move(1) end)
  bind('<Up>', function() move(-1) end)
  bind('h', function()
    if expanded[selected] and #nodes[selected].children > 0 then expanded[selected] = nil
    elseif nodes[selected].parent then
      if selected == root then root = nodes[selected].parent end
      selected = nodes[selected].parent
      expanded[selected] = true
    end
  end)
  bind('l', function()
    if #nodes[selected].children == 0 then return end
    if not expanded[selected] then expanded[selected] = true
    else selected = nodes[selected].children[1] end
  end)
  for _, key in ipairs({'<Esc>', 'q', 't'}) do
    vim.keymap.set('n', key, function() dispose(); callbacks.close() end, {buffer = buffer, silent = true})
  end
  vim.keymap.set('n', '<CR>', function() callbacks.choose(selected) end, {buffer = buffer, silent = true})
  return {window = window, buffer = buffer, dispose = dispose,
    resize = function() if api.nvim_win_is_valid(window) then api.nvim_win_set_config(window, config()); draw() end end,
    state = function() return {layout = 'vertical', root = root, selected = selected} end}
end
return M
