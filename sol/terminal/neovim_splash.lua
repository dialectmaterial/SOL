-- The start-up placeholder: Neovim starts while Python restores the position
-- and builds the first page, then asks for that page once and loads it. It
-- shows no book text; a start-up failure closes Neovim and Python reports it.
return function(reader)
  local api = vim.api
  local fail = reader.text.fail
  local input = assert(io.open(vim.env.SOL_NVIM_INPUT, 'r'))
  local ok, data = pcall(vim.json.decode, input:read('*a'))
  input:close()
  if not ok or type(data) ~= 'table' or data.pending ~= true or type(data.message) ~= 'string' then
    fail('invalid start-up placeholder')
  end
  local buffer = api.nvim_get_current_buf()
  local lines = {}
  for _ = 1, math.max(0, math.floor((vim.o.lines - 2) / 2) - 1) do lines[#lines + 1] = '' end
  local message = data.message
  lines[#lines + 1] = string.rep(' ', math.max(0, math.floor((vim.o.columns - vim.fn.strdisplaywidth(message)) / 2)))
    .. message
  api.nvim_buf_set_lines(buffer, 0, -1, false, lines)
  vim.bo[buffer].modifiable, vim.bo[buffer].modified = false, false
  vim.o.laststatus, vim.o.ruler, vim.o.showmode = 0, false, false
  vim.wo.number, vim.wo.relativenumber, vim.wo.cursorline = false, false, false
  api.nvim_buf_add_highlight(buffer, -1, 'Comment', #lines - 1, 0, -1)
  vim.cmd('redraw')
  for _, key in ipairs({ 'q', '<C-c>' }) do
    vim.keymap.set('n', key, function() vim.cmd('qa!') end, { buffer = buffer, silent = true })
  end

  local channel = reader.load('neovim_channel')(fail)
  if not channel then fail('the start-up placeholder needs the installed SOL reader') end
  channel.serial = channel.serial + 1
  local id = channel.serial
  channel.navigation_pending = id
  channel.pending[id] = function(result, problem)
    channel.navigation_pending = nil
    if result and result.cancel == true then
      -- SOL needs the plain terminal first (a question or an error message).
      vim.cmd('qa!')
      return
    end
    if not result or type(result.payload) ~= 'table' then
      -- Python prints the reason once Neovim has closed.
      vim.cmd('cquit 3')
      return
    end
    reader.reload(result.payload)
    if api.nvim_buf_is_valid(buffer) then
      vim.bo[buffer].modifiable = true
      api.nvim_buf_set_lines(buffer, 0, -1, false, {})
      vim.bo[buffer].modifiable, vim.bo[buffer].modified = false, false
    end
  end
  channel.writer:write(vim.json.encode({ id = id, op = 'initial' }) .. '\n')
end
