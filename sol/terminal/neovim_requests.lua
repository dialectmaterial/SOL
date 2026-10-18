-- Process-local action channel, response dispatch and view reloads.
return function(reader)
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

  local channel = reader.load('neovim_channel')(fail)
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
