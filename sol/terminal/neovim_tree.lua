-- On-demand orientation: an expandable outline or a horizontal column browser.
-- Labels/paths are presentation; only Python resolves a chosen node to a source ID.
local M, api = {}, vim.api
function M.open(structure, callbacks)
  local nodes = {}
  for _, node in ipairs(structure.nodes) do nodes[node.key] = node end
  local current = assert(nodes[structure.current], 'current source branch is not in the tree')
  local preferences = rawget(_G, 'SOLTreePreferences') or {}
  local layout, depth = preferences.layout or 'vertical', preferences.depth or structure.depth or 2
  local root, selected, expanded = structure.root or (nodes[structure.doctrine] and structure.doctrine or '/'), current.key, {}
  local buffer = api.nvim_create_buf(false, true)
  vim.bo[buffer].buftype, vim.bo[buffer].bufhidden = 'nofile', 'wipe'
  local window, rows, cursor_row, cursor_byte
  local function inside(key, value)
    return key == '/' or key == value or value:sub(1, #key + 1) == key .. '/'
  end
  local function label(node)
    local mark = node.key == current.key and '* ' or inside(node.key, current.key) and '> ' or '  '
    return mark .. node.title:gsub('%s+', ' ')
  end
  local function reset_scope(key)
    root, selected, expanded = key, inside(key, current.key) and current.key or key, {}
    local function expand(at, remaining)
      if remaining <= 0 or #nodes[at].children == 0 then return end
      expanded[at] = true
      for _, child in ipairs(nodes[at].children) do expand(child, remaining - 1) end
    end
    expand(key, depth)
  end
  local function config()
    return {relative = 'editor', row = 1, col = 1, width = math.max(1, vim.o.columns - 4),
      height = math.max(1, vim.o.lines - 4), style = 'minimal', border = 'single', zindex = 60}
  end
  local function fit(text, width)
    if vim.fn.strdisplaywidth(text) > width then
      while vim.fn.strdisplaywidth(text) > math.max(0, width - 1) do text = vim.fn.strcharpart(text, 0, vim.fn.strchars(text) - 1) end
      text = text .. '~'
    end
    return text .. string.rep(' ', math.max(0, width - vim.fn.strdisplaywidth(text)))
  end
  local function draw()
    if not api.nvim_buf_is_valid(buffer) then return end
    local lines = {
      'Tree | ' .. layout .. ' | depth ' .. depth .. ' | * here, > contains current passage',
      'Tab layout | j/k move | h/l collapse/expand or parent/child | Enter read',
      'r doctrine | b current branch | w whole work | +/- depth | Esc return',
      'Reading: ' .. current.key, 'Selected: ' .. selected .. ' | ' .. nodes[selected].title:gsub('%s+', ' '), '',
    }
    rows, cursor_row, cursor_byte = {}, nil, 0
    if layout == 'vertical' then
      local visible = {}
      local function visit(key, indent, prefix)
        visible[#visible + 1] = key
        lines[#lines + 1] = prefix .. (#nodes[key].children > 0 and (expanded[key] and '[-] ' or '[+] ') or '    ') .. label(nodes[key])
        rows[#lines] = key
        if key == selected then cursor_row = #lines end
        if expanded[key] then
          for index, child in ipairs(nodes[key].children) do
            visit(child, indent + 1, string.rep('  ', indent) .. (index == #nodes[key].children and '`- ' or '|- '))
          end
        end
      end
      visit(root, 1, '')
      while not cursor_row and selected ~= root do selected = nodes[selected].parent or root; return draw() end
    else
      local ancestry, at = {}, selected
      while at do
        table.insert(ancestry, 1, at)
        if at == root then break end
        at = nodes[at].parent
      end
      local columns = {{root}}
      for _, key in ipairs(ancestry) do
        if #nodes[key].children > 0 then columns[#columns + 1] = nodes[key].children end
      end
      local width = config().width
      local count = math.max(1, math.min(depth + 1, math.floor(width / 24)))
      if count == 1 and #nodes[selected].children > 0 then table.remove(columns) end
      local first = math.max(1, #columns - count + 1)
      count = #columns - first + 1
      local column_width, height = math.max(1, math.floor(width / count)), 0
      for index = first, #columns do height = math.max(height, #columns[index]) end
      for row = 1, height do
        local line = ''
        for column = first, #columns do
          local key = columns[column][row]
          if key == selected then cursor_row, cursor_byte = #lines + 1, #line end
          line = line .. fit(key and ((key == selected and '[ ' or '  ') .. label(nodes[key])) or '', column_width)
        end
        lines[#lines + 1] = line
      end
    end
    vim.bo[buffer].modifiable = true
    api.nvim_buf_set_lines(buffer, 0, -1, false, lines)
    vim.bo[buffer].modifiable, vim.bo[buffer].readonly = false, true
    if window and api.nvim_win_is_valid(window) then
      api.nvim_win_set_cursor(window, {cursor_row or 7, cursor_byte})
    end
    preferences.layout, preferences.depth = layout, depth
    _G.SOLTreePreferences = preferences
  end
  reset_scope(root)
  draw()
  window = api.nvim_open_win(buffer, true, config())
  vim.wo[window].wrap, vim.wo[window].cursorline = false, true
  vim.wo[window].scrolloff = 2
  draw()
  local function dispose()
    if window and api.nvim_win_is_valid(window) then api.nvim_win_close(window, true) end
    if api.nvim_buf_is_valid(buffer) then api.nvim_buf_delete(buffer, {force = true}) end
  end
  local function bind(key, action)
    vim.keymap.set('n', key, function() action(); draw() end, {buffer = buffer, silent = true})
  end
  local function siblings(delta)
    if layout == 'vertical' then
      local line = api.nvim_win_get_cursor(window)[1]
      local at = line + delta
      while at > 0 and at <= api.nvim_buf_line_count(buffer) do
        if rows[at] then selected = rows[at]; return end
        at = at + delta
      end
    else
      local parent = selected ~= root and nodes[selected].parent
      local family = parent and nodes[parent].children or {root}
      for index, key in ipairs(family) do
        if key == selected then selected = family[index + delta] or selected; return end
      end
    end
  end
  bind('j', function() siblings(1) end)
  bind('k', function() siblings(-1) end)
  bind('h', function()
    if layout == 'vertical' and expanded[selected] then expanded[selected] = nil
    elseif selected ~= root then selected = nodes[selected].parent or root end
  end)
  bind('l', function()
    if #nodes[selected].children == 0 then return end
    if layout == 'vertical' and not expanded[selected] then expanded[selected] = true
    else selected = nodes[selected].children[1] end
  end)
  bind('<Tab>', function()
    layout = layout == 'vertical' and 'horizontal' or 'vertical'
    if layout == 'vertical' then
      local at = selected
      while at ~= root and nodes[at].parent do
        at = nodes[at].parent; expanded[at] = true
      end
    end
  end)
  bind('r', function() reset_scope(nodes[structure.doctrine] and structure.doctrine or '/') end)
  bind('b', function() reset_scope(current.parent or current.key) end)
  bind('w', function() reset_scope('/') end)
  bind('+', function() depth = math.min(6, depth + 1); reset_scope(root) end)
  bind('-', function() depth = math.max(1, depth - 1); reset_scope(root) end)
  for _, key in ipairs({'<Esc>', 'q', 't'}) do
    vim.keymap.set('n', key, function() dispose(); callbacks.close() end, {buffer = buffer, silent = true})
  end
  vim.keymap.set('n', '<CR>', function() callbacks.choose(selected) end, {buffer = buffer, silent = true})
  return {window = window, buffer = buffer, dispose = dispose,
    resize = function() if api.nvim_win_is_valid(window) then api.nvim_win_set_config(window, config()); draw() end end,
    state = function() return {layout = layout, depth = depth, root = root, selected = selected} end}
end
return M
