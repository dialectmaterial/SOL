-- The private action channel to Python: inherited pipes, created once per
-- Neovim process and shared by the start-up placeholder and every reader view.
return function(fail)
  local uv = vim.uv or vim.loop
  -- Inherited pipes carry bounded data requests to the existing Python owner.
  -- They survive view reloads, unlike buffers; no listener or user config exists.
  local channel = rawget(_G, 'SOLReaderChannel')
  if not channel and vim.env.SOL_NVIM_REQUEST_FD and vim.env.SOL_NVIM_RESPONSE_FD then
    channel = { serial = 0, pending = {}, incoming = '' }
    channel.writer, channel.reader = uv.new_pipe(false), uv.new_pipe(false)
    assert(channel.writer:open(tonumber(vim.env.SOL_NVIM_REQUEST_FD)))
    assert(channel.reader:open(tonumber(vim.env.SOL_NVIM_RESPONSE_FD)))
    channel.reader:read_start(vim.schedule_wrap(function(problem, chunk)
      if problem or not chunk then
        for _, callback in pairs(channel.pending) do callback(nil, 'SOL action channel closed; no save acknowledged') end
        channel.pending = {}
        channel.navigation_pending = nil
        return
      end
      channel.incoming = channel.incoming .. chunk
      if #channel.incoming > 16 * 1024 * 1024 then fail('reader response exceeds budget') end
      while channel.incoming:find('\n', 1, true) do
        local at = channel.incoming:find('\n', 1, true)
        local line = channel.incoming:sub(1, at - 1)
        channel.incoming = channel.incoming:sub(at + 1)
        local ok, reply = pcall(vim.json.decode, line)
        if ok and type(reply) == 'table' then
          local callback = channel.pending[reply.id]
          channel.pending[reply.id] = nil
          if callback then callback(reply.ok and reply.result or nil, reply.error) end
        end
      end
    end))
    _G.SOLReaderChannel = channel
  end
  return channel
end
