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
  local function config()
    return {relative = 'editor', row = 1, col = 1, width = math.max(1, vim.o.columns - 4),
      height = math.max(1, vim.o.lines - 4), style = 'minimal', border = 'single', zindex = 60}
  end
  local function draw()
    local lines = {'Book outline | * current branch',
      'j/k move | h parent/collapse | l expand/child | Enter read | Esc return',
      'Reading: ' .. current.key, ''}
    local cursor_row
    rows = {}
    local function visit(key, level)
      local node = nodes[key]
      lines[#lines + 1] = string.rep('  ', level) ..
        (#node.children == 0 and '    ' or expanded[key] and '[-] ' or '[+] ') ..
        (key == current.key and '* ' or '  ') .. node.title:gsub('%s+', ' ')
      rows[#lines] = key
      if key == selected then cursor_row = #lines end
      if expanded[key] then for _, child in ipairs(node.children) do visit(child, level + 1) end end
    end
    visit(root, 0)
    vim.bo[buffer].readonly, vim.bo[buffer].modifiable = false, true
    api.nvim_buf_set_lines(buffer, 0, -1, false, lines)
    vim.bo[buffer].modifiable, vim.bo[buffer].readonly = false, true
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
