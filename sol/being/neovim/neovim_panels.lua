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
    if (closing or packet) and api.nvim_win_is_valid(window) then api.nvim_set_current_win(window) end
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
      vim.wo[panels.window].breakindent, vim.wo[panels.window].breakindentopt = true, 'min:0,shift:' .. hanging
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
  local show_search, show_source, show_pdf, show_landmarks
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
  -- Named landmarks: the workspace's bookmarks, or this session's when temporary.
  -- Naming one only echoes; list edits keep the reader's position untouched.
  show_landmarks = function(result)
    if result.action == 'set' then
      api.nvim_echo({{'Landmark "' .. result.name .. '" is here' ..
        (result.persistent and '' or ' for this session'), 'None'}}, false, {})
      return
    end
    local lines = {'Landmarks — ' .. (result.order == 'book' and 'book order' or 'name order') ..
      (result.persistent and '' or ' (this session only)'), ''}
    local rows = {}
    for _, item in ipairs(result.rows) do
      lines[#lines + 1] = item.name
      rows[#lines] = item
      lines[#lines + 1] = '   ' .. item.label
      rows[#lines] = item
    end
    if #result.rows == 0 then lines[#lines + 1] = 'None yet: M names the place you are reading.' end
    lines[#lines + 1] = ''
    lines[#lines + 1] = 'Enter reads a landmark; D forgets it.'
    lines[#lines + 1] = 'r renames; o toggles name/book order (session only).'
    lines[#lines + 1] = 'Esc returns unchanged.'
    show_lines(lines, nil, {{1, 'SOLSourceHeading'}})
    local panel = api.nvim_get_current_buf()
    if #result.rows > 0 then api.nvim_win_set_cursor(panels.window, {3, 0}) end
    if result.action == 'renamed' then
      for index, item in ipairs(result.rows) do
        if item.name == result.name then api.nvim_win_set_cursor(panels.window, {index * 2 + 1, 0}); break end
      end
    end
    local function chosen()
      return rows[api.nvim_win_get_cursor(panels.window)[1]]
    end
    vim.keymap.set('n', '<CR>', function()
      local item = chosen()
      if not item then return end
      if not item.available then vim.notify('That landmark\'s paragraph is unavailable', vim.log.levels.WARN); return end
      close_popup(); request('landmark_open', {name = item.name})
    end, {buffer = panel, silent = true})
    vim.keymap.set('n', 'D', function()
      local item = chosen()
      if item then request('landmark_clear', {name = item.name}) end
    end, {buffer = panel, silent = true})
    vim.keymap.set('n', 'r', function()
      local item = chosen()
      if not item then return end
      local ok, name = pcall(vim.fn.input, 'Rename landmark: ', item.name)
      api.nvim_echo({{'', 'None'}}, false, {})
      if ok then request('landmark_rename', {name = item.name, new_name = name}) end
    end, {buffer = panel, silent = true})
    vim.keymap.set('n', 'o', function() request('landmark_order') end, {buffer = panel, silent = true})
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
    if result.pdf_missing then
      lines[#lines + 1] = 'No PDF viewer is available (install Zathura, or set SOL_PDF_VIEWER), so this is the crop.'
    end
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
    lines[#lines + 1] = 'S opens the whole page in a PDF viewer, to zoom and read it in context.'
    lines[#lines + 1] = (#result.pages > 1 and 'A page number shows that page. ' or '') .. 'Esc returns to reading.'
    show_lines(lines)
    local panel = api.nvim_get_current_buf()
    local shown = result.shown
    vim.keymap.set('n', 'S', function() request('source_pdf', {page = shown}) end, {buffer = panel, silent = true})
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
  -- The printed page itself, zoomable and in context, in a PDF viewer beside the
  -- reader; without a viewer Python sends the crop instead. The position never moves.
  -- After S opens Zathura, it follows the passage the reader rests on, until it
  -- is closed. Moves are debounced and never wait for, or move, the reader.
  -- Kept beside the request channel, so it survives section reloads.
  local follow = rawget(_G, 'SOLReaderFollow') or {active = false, last = nil, timer = nil}
  _G.SOLReaderFollow = follow
  local function resting_passage()
    local ok, packet = pcall(current_packet)
    return ok and packet and packet.reference.reference.target_id or nil
  end
  show_pdf = function(result)
    api.nvim_echo({{'Printed page ' .. result.printed_page .. ' (PDF page ' .. result.pdf_page ..
      ') in ' .. result.viewer .. (result.viewer == 'zathura' and '; it follows your reading' or ''), 'None'}},
      false, {})
    follow.active, follow.last = result.viewer == 'zathura', resting_passage()
  end
  function panels.stop_follow() follow.active = false end
  function panels.update_follow(result) follow.active = follow.active and result.active == true end
  function panels.follow_tick()
    if not follow.active then return end
    if follow.timer then follow.timer:stop() end
    follow.timer = vim.defer_fn(function()
      follow.timer = nil
      local channel = rawget(_G, 'SOLReaderChannel')
      if not follow.active or panels.window or api.nvim_get_current_win() ~= window
        or (channel and channel.navigation_pending) then return end
      local passage = resting_passage()
      if passage and passage ~= follow.last then
        follow.last = passage
        request('source_follow')
      end
    end, 400)
  end
  local function source_pdf()
    request('source_pdf', {page = 1})
  end

  panels.close_popup, panels.show_lines, panels.current_packet = close_popup, show_lines, current_packet
  panels.side_config = side_config
  panels.show_search, panels.show_source, panels.show_landmarks = show_search, show_source, show_landmarks
  panels.source, panels.source_pdf, panels.show_pdf = source, source_pdf, show_pdf
  return panels
end
