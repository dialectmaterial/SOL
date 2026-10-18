-- Process-local action channel, response dispatch and view reloads.
return function(reader)
  local uv = vim.uv or vim.loop
  local fail = reader.text.fail
  local data = reader.view.data
  local mode = reader.view.mode
  local current_packet = reader.panels.current_packet
  local function reload(payload)
    return reader.reload(payload)
  end
  local function toggle_mode()
    local active_channel = rawget(_G, 'SOLReaderChannel')
    if active_channel and active_channel.navigation_pending then fail('wait for the reading location to finish loading') end
    local packet = current_packet()
    local payload = vim.deepcopy(data)
    payload.restore, payload.mode, payload.tree_only = packet, mode == 'paragraph' and 'continuous' or 'paragraph', false
    reload(payload)
  end
  local function toggle_focus()
    local active_channel = rawget(_G, 'SOLReaderChannel')
    if active_channel and active_channel.navigation_pending then fail('wait for the reading action to finish') end
    local payload = vim.deepcopy(data)
    payload.restore, payload.focus = current_packet(), not data.focus
    reload(payload)
  end

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
  local function request(operation, fields, callback, packet)
    if not channel then fail('this action needs the installed SOL reader, not a research export') end
    if channel.navigation_pending then return end
    local message = vim.deepcopy(fields or {})
    channel.serial = channel.serial + 1
    message.id, message.op, message.packet, message.mode = channel.serial, operation, packet or current_packet(), mode
    message.focus = data.focus == true
    if data.theme then message.theme = data.theme.active end
    if operation ~= 'marker_set' and operation ~= 'marker_clear' then
      channel.navigation_pending = message.id
    end
    channel.pending[message.id] = function(result, problem)
      if channel.navigation_pending == message.id then channel.navigation_pending = nil end
      if not result then vim.notify(tostring(problem), vim.log.levels.ERROR); return end
      local ok, error = pcall(function()
        if result.payload then reload(result.payload)
        elseif result.search then reader.panels.show_search(result.search)
        elseif result.source then reader.panels.show_source(result.source)
        elseif result.study then reader.panels.show_study(result.study)
        elseif result.note_history then reader.notes.show_history(result.note_history)
        elseif result.essence then reader.essence.open(result.essence)
        elseif result.personal then _G.SOLNvimReader.update_personal(result.personal)
        elseif result.markers then
          _G.SOLNvimReader.update_markers(result.markers)
          vim.api.nvim_echo({{'Markers updated' .. (result.markers.persistent and '' or ' for this temporary session'), 'None'}}, false, {})
        end
        if callback then callback(result) end
      end)
      if not ok then vim.notify(tostring(error), vim.log.levels.ERROR) end
    end
    channel.writer:write(vim.json.encode(message) .. '\n', vim.schedule_wrap(function(problem)
      if problem then
        local callback = channel.pending[message.id]
        channel.pending[message.id] = nil
        if callback then callback(nil, tostring(problem)) end
      end
    end))
  end

  return {request = request, reload = reload, toggle_mode = toggle_mode, toggle_focus = toggle_focus}
end
