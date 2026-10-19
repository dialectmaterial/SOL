-- Personal-note editor, process-local draft recovery and note history.
return function(reader)
  local api = vim.api
  local fail = reader.text.fail
  local data = reader.view.data
  local by_id = reader.view.by_id
  local normal_escape = reader.view.normal_escape
  local restore = reader.view.restore
  local close_popup = reader.panels.close_popup
  local show_lines = reader.panels.show_lines
  local current_packet = reader.panels.current_packet
  local panels = reader.panels
  local request = reader.requests.request
  -- A personal note binds the whole passage through the workspace service. A
  -- selection is shown as context above the editor and is not stored. Drafts
  -- survive any close except an explicit discard, and an unacknowledged save.
  -- With `edit`, the same editor revises an existing note from the revision shown.
  local note_namespace = api.nvim_create_namespace('sol-note')
  local function note(edit)
    if not data.personal then fail('notes need the installed SOL reader') end
    if not data.personal.persistent then fail('notes need a workspace; this temporary -n session saves nothing') end
    if edit and edit.edit_refusal ~= '' then fail(edit.edit_refusal) end
    local packet = current_packet()
    local record = by_id[packet.reference.reference.target_id]
    local key = edit and ('edit:' .. edit.id) or record.id
    if vim.fn.mode(1) ~= 'n' then normal_escape() end
    close_popup()
    if vim.fn.mode(1) ~= 'n' then normal_escape() end
    local channel_state = rawget(_G, 'SOLReaderChannel')
    local drafts = channel_state and channel_state.drafts or {}
    if channel_state then channel_state.drafts = drafts end
    local editor = api.nvim_create_buf(false, true)
    vim.bo[editor].buftype, vim.bo[editor].bufhidden = 'acwrite', 'wipe'
    api.nvim_buf_set_name(editor, 'sol://note/' .. record.id .. '/' .. editor)
    local initial = drafts[key] or (edit and edit.body)
    if initial then
      api.nvim_buf_set_lines(editor, 0, -1, false, vim.split(initial, '\n', { plain = true }))
    end
    vim.bo[editor].modified = false
    -- Beside the passage when there is room, as the context panel is.
    local side = panels.side_config()
    local columns = reader.view.reader_columns()
    local width = side and side.width or math.max(20, math.min(data.width, columns - 6))
    local quote = {}
    if packet.selection ~= vim.NIL then
      local text, line = packet.selection.text:gsub('%s+', ' '), ''
      -- One character at a time; in Lua, '\\zs' must be escaped to reach Vim.
      for _, char in ipairs(vim.fn.split(text, '\\zs')) do
        if vim.fn.strdisplaywidth(line .. char) > width - 2 then
          quote[#quote + 1] = line; line = ''
          if #quote == 3 then quote[3] = vim.fn.strcharpart(quote[3], 0, vim.fn.strchars(quote[3]) - 1) .. '…'; break end
        end
        line = line .. char
      end
      if #quote < 3 and line ~= '' then quote[#quote + 1] = line end
    end
    local config = side or { relative = 'editor', row = 3, col = math.max(0, math.floor((columns - width) / 2)),
      width = width, height = math.max(3, math.min(12 + #quote, vim.o.lines - 10)) }
    config.style, config.border, config.zindex = 'minimal', 'single', 50
    config.title = edit and (' Edit your note (revision ' .. tostring(edit.revision) .. ') ')
      or (' Note on: ' .. vim.fn.strcharpart(record.heading, 0, width - 14) .. ' ')
    config.title_pos, config.footer, config.footer_pos = 'left', ' Ctrl-S or :w saves · Ctrl-C discards ', 'right'
    panels.window = api.nvim_open_win(editor, true, config)
    vim.wo[panels.window].wrap, vim.wo[panels.window].linebreak = true, true
    vim.wo[panels.window].winhighlight = 'NormalFloat:SOLPanel,FloatBorder:SOLPanelBorder'
    if #quote > 0 then
      local lines = {}
      for _, row in ipairs(quote) do lines[#lines + 1] = { { row, 'Comment' } } end
      lines[#lines + 1] = { { '(selection shown for context; the note attaches to the passage)', 'Comment' } }
      api.nvim_buf_set_extmark(editor, note_namespace, 0, 0, { virt_lines = lines, virt_lines_above = true })
      vim.fn.winrestview({ topfill = #lines })
    end
    local finished = false
    local function body()
      return table.concat(api.nvim_buf_get_lines(editor, 0, -1, false), '\n')
    end
    api.nvim_create_autocmd('BufWipeout', { buffer = editor, once = true, callback = function()
      if not finished and body():match('%S') and (not edit or body() ~= edit.body) then
        drafts[key] = body()
        local again = edit and 'e on the note in c' or 'a on this passage'
        vim.schedule(function() api.nvim_echo({ { 'Note draft kept; press ' .. again .. ' to continue it', 'WarningMsg' } }, false, {}) end)
      end
    end })
    local function save()
      local text = body()
      if not text:match('%S') then fail('empty note; nothing saved') end
      -- Keep the draft until Python acknowledges the save.
      drafts[key], finished = text, true
      vim.cmd('stopinsert')
      close_popup()
      restore(packet)
      if edit then
        request('note_edit', { note = edit.id, revision = edit.revision, body = text }, function(result)
          drafts[key] = nil
          local saved = result.note_saved
          api.nvim_echo({ { saved.changed and ('Note revised (revision ' .. tostring(saved.revision) .. ')')
            or 'Note unchanged; no new revision', 'None' } }, false, {})
        end)
      else
        request('note_add', { body = text }, function()
          drafts[key] = nil
          api.nvim_echo({ { 'Note saved in your workspace', 'None' } }, false, {})
        end)
      end
    end
    local function discard()
      drafts[key], finished = nil, true
      vim.cmd('stopinsert')
      close_popup()
      restore(packet)
    end
    api.nvim_create_autocmd('BufWriteCmd', { buffer = editor, callback = function()
      local ok, problem = pcall(save)
      if not ok then vim.notify(tostring(problem), vim.log.levels.ERROR) end
    end })
    for _, key_mode in ipairs({ 'n', 'i' }) do
      vim.keymap.set(key_mode, '<C-s>', function()
        local ok, problem = pcall(save)
        if not ok then vim.notify(tostring(problem), vim.log.levels.ERROR) end
      end, { buffer = editor, silent = true })
      vim.keymap.set(key_mode, '<C-c>', discard, { buffer = editor, silent = true })
    end
    vim.cmd('startinsert')
    return editor
  end
  local function show_note_history(history)
    local lines = { "Versions of a note by " .. history.author .. ", newest first", "" }
    for _, item in ipairs(history.revisions) do
      lines[#lines + 1] = "Revision " .. tostring(item.revision) .. " (" .. item.kind .. "), " ..
        item.editor .. ", " .. item.recorded_at
      for _, line in ipairs(item.lines) do lines[#lines + 1] = "  " .. line end
      lines[#lines + 1] = ""
    end
    if #history.revisions == 0 then lines[#lines + 1] = "This older workspace keeps no versions." end
    lines[#lines + 1] = "Esc returns to reading."
    show_lines(lines)
  end

  return {note = note, show_history = show_note_history}
end
