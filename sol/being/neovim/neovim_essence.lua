-- ESSENCE beside or over the reader: one Textual process in a terminal float.
-- Neovim owns this outer layout (split, fullscreen, hidden); the app owns its
-- inside. State lives in _G.SOLEssence so the process and its window survive
-- reader reloads. Closing ESSENCE refocuses the reader, whose cursor and
-- selection were never touched.
return function(reader)
  local api = vim.api
  local fail = reader.text.fail
  local state = rawget(_G, 'SOLEssence')
  if not state then
    state = {}
    _G.SOLEssence = state
  end
  -- Below this many columns ESSENCE cannot sit beside a readable page.
  local SPLIT_MINIMUM = 100
  -- ESSENCE asks the reader to open a source with this private OSC; the
  -- reader's ordinary checked navigation decides whether it may.
  local SOURCE_PREFIX = '\27]5379;sol-essence;'
  -- How long quitting the reader waits for ESSENCE to save its state.
  local SAVE_WAIT_MS = 2000
  local input_namespace = api.nvim_create_namespace('SOLEssenceInput')

  local function alive()
    return state.window ~= nil and api.nvim_win_is_valid(state.window)
  end
  local function reader_window()
    local current = rawget(_G, 'SOLNvimReader')
    return current and current.window and api.nvim_win_is_valid(current.window) and current.window or nil
  end
  local function passage_location(packet)
    local records = reader.view.data.records
    return packet.reference.reference.target_id .. ':' .. records[1].id .. ':' .. records[#records].id
  end
  -- Only passage/section changes need a fresh CORE capture. Cursor and selection
  -- changes inside that passage never publish. The timer retries failed changes
  -- quietly and survives reloads; this function is rebound to the current view.
  function state.follow_tick()
    local channel = rawget(_G, 'SOLReaderChannel')
    if not state.job or not state.position_file or state.position_busy
        or not channel or channel.navigation_pending or not alive()
        or api.nvim_get_current_win() ~= reader_window() then return end
    local ok, packet = pcall(reader.panels.current_packet)
    if not ok or not packet then return end
    local location = passage_location(packet)
    if location == state.position_location then return end
    local now = (vim.uv or vim.loop).now()
    if location == state.position_attempt and now - (state.position_time or 0) < 500 then return end
    local position_file = state.position_file
    state.position_busy = true
    state.position_time, state.position_attempt = now, location
    local sent = pcall(reader.requests.request, 'essence_position', nil, function(result)
      if state.position_file ~= position_file then return end
      state.position_busy = false
      if result then state.position_location = location end
    end, packet)
    if not sent then state.position_busy = false end
  end
  -- ESSENCE follows the reader's theme by reading this owner-only file, which
  -- Python created beside its context; replaced whole so it is never half-written.
  function state.set_theme(name)
    if not state.theme_file or type(name) ~= 'string' or not name:match('^[a-z]+$') then return end
    local temporary = state.theme_file .. '.tmp'
    local descriptor = vim.uv.fs_open(temporary, 'w', tonumber('600', 8))
    if not descriptor then return end
    vim.uv.fs_write(descriptor, name)
    vim.uv.fs_close(descriptor)
    vim.uv.fs_rename(temporary, state.theme_file)
  end
  local function split_width()
    return math.max(40, math.floor(vim.o.columns * 0.45))
  end
  -- Columns the reader leaves free on the right: only while ESSENCE is beside it.
  function state.reserved()
    return (state.layout == 'split' and alive()) and split_width() + 1 or 0
  end
  local function config()
    local height = math.max(1, vim.o.lines - 2)
    if state.layout == 'full' then
      return { relative = 'editor', row = 0, col = 0, width = vim.o.columns, height = height,
        style = 'minimal', border = 'none', zindex = 40, hide = false }
    end
    local width = split_width()
    return { relative = 'editor', row = 0, col = math.max(0, vim.o.columns - width - 1), width = width,
      height = height, style = 'minimal', border = { '', '', '', '', '', '', '', '│' }, zindex = 40,
      hide = state.layout == 'hidden' }
  end
  local function relayout()
    if alive() then api.nvim_win_set_config(state.window, config()) end
    local current = rawget(_G, 'SOLNvimReader')
    if current and current.relayout then current.relayout() end
  end
  -- Back to the reader at the position and selection E captured, once.
  local function return_to_reader()
    local origin = state.origin
    state.origin = nil
    local window = reader_window()
    if window then api.nvim_set_current_win(window) end
    local current = rawget(_G, 'SOLNvimReader')
    -- After a section change the origin may not be on screen; then stay put.
    if origin and current then pcall(current.restore, origin) end
  end
  local function enter()
    api.nvim_set_current_win(state.window)
    vim.cmd('startinsert')
  end

  function state.focus()
    if not alive() then return end
    -- E may refocus the old terminal just before its exit callback runs.
    state.reopen = true
    if state.layout == 'hidden' then
      state.layout = vim.o.columns >= SPLIT_MINIMUM and 'split' or 'full'
      relayout()
    end
    enter()
  end

  function state.toggle()
    if not alive() then return end
    if state.layout == 'full' then
      if vim.o.columns < SPLIT_MINIMUM then
        vim.notify('The terminal is too narrow to show ESSENCE beside the reader', vim.log.levels.WARN)
        return
      end
      state.layout = 'split'
    else
      state.layout = 'full'
    end
    relayout()
    enter()
  end

  function state.back_to_reader()
    if not alive() then return end
    if state.layout == 'full' then
      state.layout = vim.o.columns >= SPLIT_MINIMUM and 'split' or 'hidden'
      relayout()
    end
    vim.cmd('stopinsert')
    return_to_reader()
  end

  -- Show the reader without returning to the origin: a source opens there.
  local function reveal_reader()
    if state.layout == 'full' then
      state.layout = vim.o.columns >= SPLIT_MINIMUM and 'split' or 'hidden'
      relayout()
    end
    vim.cmd('stopinsert')
    local window = reader_window()
    if window then api.nvim_set_current_win(window) end
  end

  -- The request ESSENCE encoded, or nil and why it is refused.
  local function source_request(sequence)
    if type(sequence) ~= 'string' or sequence:sub(1, #SOURCE_PREFIX) ~= SOURCE_PREFIX or #sequence > 4096 then
      return nil
    end
    local decoded, text = pcall(vim.base64.decode, sequence:sub(#SOURCE_PREFIX + 1))
    local parsed, value = pcall(vim.json.decode, decoded and text or '')
    if not decoded or not parsed or type(value) ~= 'table' or value.version ~= 1 or value.op ~= 'open_source'
        or type(value.source) ~= 'table' then
      return nil, 'ESSENCE sent an invalid source request'
    end
    local source = value.source
    local count = 0
    for _ in pairs(value) do count = count + 1 end
    for _ in pairs(source) do count = count + 1 end
    if count ~= 6 or type(source.id) ~= 'string' or not source.id:match('^%x+%-%x+%-%x+%-%x+%-%x+$')
        or type(source.start) ~= 'number' or source.start < 0 or source.start % 1 ~= 0
        or type(source.content_sha256) ~= 'string' or not source.content_sha256:match('^%x+$')
        or #source.content_sha256 ~= 64 then
      return nil, 'ESSENCE sent an invalid source request'
    end
    return { id = source.id, start = source.start, content_sha256 = source.content_sha256 }
  end

  -- Leaving terminal mode completes only after this callback returns, and the
  -- reader can capture its position only in normal mode: wait for it.
  local function when_normal(action)
    if vim.fn.mode(1) == 'n' then return action() end
    local id
    id = api.nvim_create_autocmd('ModeChanged', { callback = function()
      if vim.fn.mode(1) ~= 'n' then return end
      api.nvim_del_autocmd(id)
      if reader_window() == api.nvim_get_current_win() then vim.schedule(action) end
    end })
  end

  function state.open_source(sequence)
    local source, problem = source_request(sequence)
    if not source then
      if problem then vim.notify(problem, vim.log.levels.WARN) end
      return
    end
    reveal_reader()
    when_normal(function() reader.requests.request('essence_source', { source = source }) end)
  end

  -- Quitting the reader with ESSENCE open: let ESSENCE save as if left with q.
  function state.save_before_exit()
    if not state.job then return end
    local job = state.job
    pcall(vim.fn.chansend, job, '\17')  -- Ctrl-Q, ESSENCE's own leave key
    pcall(vim.fn.jobwait, { job }, SAVE_WAIT_MS)
  end

  function state.closed(code, message)
    local window, buffer, reopen = state.window, state.buffer, state.reopen
    state.reopen = nil
    vim.on_key(nil, input_namespace)
    state.job, state.window, state.buffer, state.layout = nil, nil, nil, nil
    state.position_file, state.position_busy, state.position_location = nil, nil, nil
    state.position_attempt, state.position_time = nil, nil
    if state.position_timer then
      state.position_timer:stop()
      state.position_timer:close()
      state.position_timer = nil
    end
    vim.cmd('stopinsert')
    if window and api.nvim_win_is_valid(window) then api.nvim_win_close(window, true) end
    if buffer and api.nvim_buf_is_valid(buffer) then api.nvim_buf_delete(buffer, { force = true }) end
    relayout()
    return_to_reader()
    if reopen and code == 0 and not message then
      when_normal(function()
        local current = rawget(_G, 'SOLNvimReader')
        if not current or api.nvim_get_current_win() ~= reader_window() then return end
        state.origin = current.capture()
        reader.requests.request('essence_open', nil, nil, state.origin)
      end)
    end
    if message or code ~= 0 then
      vim.notify(message or ('ESSENCE ended with exit code ' .. tostring(code) .. '; the reader is unchanged'),
        vim.log.levels.WARN)
    end
  end

  function state.open(spec)
    if alive() then return state.focus() end
    if type(spec) ~= 'table' or type(spec.command) ~= 'table' or #spec.command == 0 then
      fail('invalid ESSENCE launch')
    end
    for _, part in ipairs(spec.command) do
      if type(part) ~= 'string' then fail('invalid ESSENCE launch') end
    end
    if spec.env ~= nil and type(spec.env) ~= 'table' then fail('invalid ESSENCE launch') end
    if spec.theme_file ~= nil and (type(spec.theme_file) ~= 'string' or spec.theme_file:sub(1, 1) ~= '/') then
      fail('invalid ESSENCE launch')
    end
    if spec.position_file ~= nil and (type(spec.position_file) ~= 'string' or spec.position_file:sub(1, 1) ~= '/') then
      fail('invalid ESSENCE launch')
    end
    state.position_file = spec.position_file
    -- Python already published the opening packet before returning this launch.
    state.position_location = spec.position_file and state.origin and passage_location(state.origin) or nil
    state.position_attempt, state.position_time = nil, nil
    state.theme_file = spec.theme_file
    -- The reader's theme now, which may have changed since Python last heard of it.
    local live = rawget(_G, 'SOLNvimReader')
    local current = live and live.theme and live.theme()
    if current then state.set_theme(current) end
    for name, value in pairs(spec.env or {}) do
      if type(name) ~= 'string' or not name:match('^[A-Z_]+$') or type(value) ~= 'string' then
        fail('invalid ESSENCE launch')
      end
    end
    state.layout = vim.o.columns >= SPLIT_MINIMUM and 'split' or 'full'
    local buffer = api.nvim_create_buf(false, true)
    state.buffer = buffer
    state.window = api.nvim_open_win(buffer, true, config())
    vim.wo[state.window].winhighlight = 'NormalFloat:Normal,FloatBorder:WinSeparator'
    local started, job = pcall(vim.fn.jobstart, spec.command, { term = true, env = spec.env,
      on_exit = function(_, code) vim.schedule(function() if state.buffer == buffer then state.closed(code) end end) end })
    if not started or type(job) ~= 'number' or job <= 0 then
      state.closed(-1, 'ESSENCE could not start: ' .. tostring(job))
      return
    end
    state.job = job
    if state.position_file then
      state.position_timer = (vim.uv or vim.loop).new_timer()
      state.position_timer:start(100, 100, vim.schedule_wrap(function() state.follow_tick() end))
    end
    state.reopen = nil
    -- Preserve a final E typed while the child is shutting down. Still send
    -- it to the PTY: in a live input field it is ordinary text, and the next
    -- typed key cancels this intent. Programmatic restore keys do not count.
    vim.on_key(function(_, typed)
      if typed ~= '' and api.nvim_get_current_buf() == buffer then state.reopen = typed == 'E' end
    end, input_namespace)
    -- Layout keys belong to Neovim; every other key goes to ESSENCE.
    for _, key_mode in ipairs({ 't', 'n' }) do
      vim.keymap.set(key_mode, '<M-f>', state.toggle, { buffer = buffer, silent = true })
      vim.keymap.set(key_mode, '<M-r>', state.back_to_reader, { buffer = buffer, silent = true })
    end
    api.nvim_create_autocmd('TermRequest', { buffer = buffer, callback = function(event)
      local sequence = type(event.data) == 'table' and event.data.sequence or event.data
      vim.schedule(function() if state.buffer == buffer then state.open_source(sequence) end end)
    end })
    relayout()
    enter()
  end

  local group = api.nvim_create_augroup('SOLEssence', { clear = true })
  api.nvim_create_autocmd('VimResized', { group = group, callback = function()
    if alive() and state.layout == 'split' and vim.o.columns < SPLIT_MINIMUM then
      -- A focused terminal grows over the page; a reader browsing beside it
      -- keeps the page and hides ESSENCE until E brings it back.
      state.layout = api.nvim_get_current_win() == state.window and 'full' or 'hidden'
    end
    relayout()
  end })
  api.nvim_create_autocmd('VimLeavePre', { group = group, callback = function() state.save_before_exit() end })
  return state
end
