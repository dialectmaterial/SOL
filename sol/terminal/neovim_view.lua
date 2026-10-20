-- Bounded source projection, cursor/selection identity, page rendering and theme.
return function(reader, supplied)
  local api, uv = vim.api, vim.uv or vim.loop
  local fail = reader.text.fail
  local integer = reader.text.integer
  local exact_keys = reader.text.exact_keys
  local boundaries = reader.text.boundaries
  local byte_to_codepoint = reader.text.byte_to_codepoint
  local codepoint_to_byte = reader.text.codepoint_to_byte
  local slice = reader.text.slice
  local valid_styles = reader.text.valid_styles
  local valid_strings = reader.text.valid_strings
  local check_personal = reader.text.check_personal
  local input_path, output_path = vim.env.SOL_NVIM_INPUT, vim.env.SOL_NVIM_OUTPUT
  if type(input_path) ~= "string" or input_path:sub(1, 1) ~= "/"
    or type(output_path) ~= "string" or output_path:sub(1, 1) ~= "/" or input_path == output_path then
    fail("private absolute input and output paths are required")
  end
  local data
  if type(supplied) == "table" then data = supplied
  else
    local fd, read_error = uv.fs_open(input_path, "r", 0)
    if not fd then fail("cannot read private input: " .. tostring(read_error)) end
    local stat = uv.fs_fstat(fd)
    if not stat or stat.type ~= "file" or stat.size > 16 * 1024 * 1024 then
      uv.fs_close(fd); fail("input must be a regular file smaller than 16 MiB")
    end
    local raw, read_problem = uv.fs_read(fd, stat.size, 0)
    uv.fs_close(fd)
    if not raw then fail("cannot read input: " .. tostring(read_problem)) end
    local decoded
    decoded, data = pcall(vim.json.decode, raw)
    if not decoded then fail("invalid input JSON") end
  end
  if type(data) ~= "table" or type(data.records) ~= "table"
    or #data.records < 1 or #data.records > 64 then fail("invalid bounded source input") end
  if not integer(data.width) or data.width < 8 or data.width > 1000 then fail("invalid reading width") end
  if data.emphasis ~= nil and data.emphasis ~= "italic" and data.emphasis ~= "underline" then
    fail("invalid semantic emphasis presentation")
  end
  local integrated = data.integrated == true
  local mode = data.mode or "continuous"
  if mode ~= "continuous" and mode ~= "paragraph" then fail("invalid reading mode") end
  local focused_id = data.restore and data.restore ~= vim.NIL and data.restore.reference.reference.target_id or data.records[1].id
  if integrated and (not exact_keys(data.navigation, { "previous", "next" })
    or type(data.navigation.previous) ~= "boolean" or type(data.navigation.next) ~= "boolean"
    or type(data.notice) ~= "string") then fail("invalid reading navigation") end
  if data.personal ~= nil and (type(data.personal) ~= "table" or type(data.personal.persistent) ~= "boolean"
    or type(data.personal.notes) ~= "table") then fail("invalid personal notes") end
  if data.personal ~= nil then check_personal(data.personal) end
  -- Presentation presets are inert highlight data from Python, never sourced files.
  local theme_groups = {}
  for _, name in ipairs({ "Normal", "SOLPanel", "SOLPanelBorder", "SOLSourceHeading", "SOLSourceWarning",
    "StatusLine", "StatusLineNC", "Visual", "Search", "CurSearch", "IncSearch",
    "CursorLine", "ErrorMsg", "WarningMsg", "NonText", "EndOfBuffer" }) do theme_groups[name] = true end
  local theme_attributes = { fg = "color", bg = "color", ctermfg = "cterm", ctermbg = "cterm",
    bold = "flag", italic = "flag", underline = "flag", reverse = "flag" }
  local presets, theme_order = {}, {}
  if data.theme ~= nil then
    local theme = data.theme
    if not exact_keys(theme, { "active", "truecolor", "presets" }) or type(theme.truecolor) ~= "boolean"
      or type(theme.presets) ~= "table" or #theme.presets < 1 then fail("invalid reader theme") end
    for _, preset in ipairs(theme.presets) do
      if not exact_keys(preset, { "name", "label", "groups", "notice", "background" }) or type(preset.name) ~= "string"
        or not (preset.background == "" or preset.background == "light" or preset.background == "dark")
        or presets[preset.name] or type(preset.label) ~= "string" or type(preset.notice) ~= "string"
        or type(preset.groups) ~= "table" then fail("invalid reader theme preset") end
      boundaries(preset.label); boundaries(preset.notice)
      for name, attributes in pairs(preset.groups) do
        if not theme_groups[name] or type(attributes) ~= "table" then fail("invalid reader theme group") end
        for key, value in pairs(attributes) do
          local kind = theme_attributes[key]
          if not ((kind == "color" and type(value) == "string" and value:match("^#%x%x%x%x%x%x$"))
            or (kind == "cterm" and integer(value) and value >= 0 and value <= 255)
            or (kind == "flag" and type(value) == "boolean")) then fail("invalid reader theme attribute") end
        end
      end
      presets[preset.name], theme_order[#theme_order + 1] = preset, preset.name
    end
    if type(theme.active) ~= "string" or not presets[theme.active] then fail("unknown reader theme") end
  end
  local previous_reader = rawget(_G, 'SOLNvimReader')
  if previous_reader and previous_reader.dispose then previous_reader.dispose() end

  local records, by_id, positions, source_rows = data.records, {}, {}, {}
  local projection, heading_rows, warning_rows, style_runs = {}, {}, {}, {}
  local namespace = api.nvim_create_namespace("sol-research-semantic-styles")
  local function append(text)
    if type(text) ~= "string" or text:find("\n", 1, true) then fail("invalid presentation row") end
    boundaries(text)
    projection[#projection + 1] = text
    return #projection
  end
  local function append_lines(text, callback)
    local start = 1
    while true do
      local at = text:find("\n", start, true)
      local value = text:sub(start, at and at - 1 or #text)
      callback(value, append(value))
      if not at then break end
      start = at + 1
    end
  end
  local previous_heading
  append("")
  if integrated and data.notice ~= "" then
    append_lines(data.notice, function(_, row) warning_rows[#warning_rows + 1] = row end)
    append("")
  end
  for _, record in ipairs(records) do
    if type(record) ~= "table" or type(record.id) ~= "string" or by_id[record.id]
      or type(record.reference) ~= "table" or type(record.reference.reference) ~= "table"
      or record.reference.reference.target_id ~= record.id then fail("invalid or duplicate source binding") end
    local points = boundaries(record.plain_text)
    if type(record.plain_text_sha256) ~= "string" or vim.fn.sha256(record.plain_text) ~= record.plain_text_sha256 then
      fail("source text digest disagrees with the exported record")
    end
    record._length = #points - 1
    valid_styles(record.styles, record._length)
    valid_strings(record.warnings)
    if type(record.heading) ~= "string" or type(record.context) ~= "table" or type(record.notes) ~= "table" then
      fail("source context is incomplete")
    end
    boundaries(record.heading)
    by_id[record.id] = record
    if mode ~= "paragraph" or record.id == focused_id then
      if not data.focus and record.heading ~= previous_heading then
        if previous_heading then append("") end
        append_lines(record.heading, function(_, row) heading_rows[#heading_rows + 1] = row end)
        append("")
        previous_heading = record.heading
      end
      for _, warning in ipairs(record.warnings) do
        append_lines("Warning: " .. warning, function(_, row) warning_rows[#warning_rows + 1] = row end)
      end
      local position, start_cp = { rows = {} }, 0
      positions[record.id] = position
      append_lines(record.plain_text, function(text, row)
        local row_length = #boundaries(text) - 1
        local item = { row = row, start = start_cp, finish = start_cp + row_length, text = text, id = record.id }
        position.rows[#position.rows + 1], source_rows[row] = item, item
        start_cp = item.finish + 1 -- the canonical newline, not an inserted paragraph break
      end)
      position.first_row, position.last_row = position.rows[1].row, position.rows[#position.rows].row
      if type(record.callouts) ~= "table" then fail("invalid footnote callouts") end
      for _, callout in ipairs(record.callouts) do
        if type(callout) ~= "table" or not integer(callout.offset) or callout.offset < 0
          or callout.offset > record._length or type(callout.label) ~= "string" then fail("invalid footnote callout") end
        boundaries(callout.label)
      end
      for _, note in ipairs(record.notes) do
        if type(note) ~= "table" or type(note.attribution) ~= "table" or type(note.label) ~= "string" then
          fail("invalid attributed note")
        end
        boundaries(note.label)
        local note_length = #boundaries(note.plain_text) - 1
        valid_styles(note.styles, note_length)
        valid_strings(note.warnings)
      end
      append("")
    end
  end
  local frozen_records = vim.deepcopy(records)

  vim.o.modeline, vim.o.exrc = false, false
  vim.o.swapfile, vim.o.backup, vim.o.writebackup, vim.o.undofile = false, false, false, false
  vim.o.laststatus, vim.o.showtabline, vim.o.cmdheight = 3, 0, 1
  vim.o.showmode, vim.o.showcmd, vim.o.ruler, vim.o.hidden = false, false, false, true
  vim.o.mouse, vim.o.clipboard = "", ""
  -- In the reader the mouse scrolls and selects; a selection is copied when
  -- the button is released. No right-click menu.
  if integrated then vim.o.mouse, vim.o.mousemodel = "a", "extend" end
  -- No "~" past the text and no "@@@" when a paragraph continues below the window.
  vim.o.fillchars = "eob: ,lastline: "
  vim.o.statusline = " j/k lines   [p/]p passages   / search   v select   c source/notes   ? help   q return"
  if integrated then
    local progress = data.progress
    if progress ~= nil and (type(progress) ~= "table" or not exact_keys(progress, { "first", "total" })
        or not integer(progress.first) or not integer(progress.total) or progress.first < 0
        or progress.total < 1 or progress.first >= progress.total) then
      fail("invalid reading progress")
    end
    vim.o.statusline = "%!v:lua.SOLStatus()"
  end
  vim.o.selection = "inclusive"
  vim.o.hlsearch = true
  -- Native visible escaping, not replacement source text. C1 source scalars keep
  -- their one-codepoint identity even when presented as a four-cell <xx> marker.
  vim.o.display = "lastline,uhex"
  local buffer = api.nvim_create_buf(false, true)
  api.nvim_buf_set_lines(buffer, 0, -1, false, projection)
  vim.bo[buffer].buftype, vim.bo[buffer].bufhidden, vim.bo[buffer].filetype = "nofile", "hide", "sol-reader"
  vim.bo[buffer].swapfile, vim.bo[buffer].undofile = false, false
  vim.bo[buffer].modifiable, vim.bo[buffer].readonly = false, true

  -- ESSENCE beside the reader takes the right-hand columns; the page and its
  -- popups centre in the rest.
  local function reader_columns()
    local essence = rawget(_G, "SOLEssence")
    return math.max(1, vim.o.columns - (essence and essence.reserved and essence.reserved() or 0))
  end
  -- Columns a side panel takes to the right of the page; the page and panel
  -- then centre together instead of the page alone.
  local side = 0
  local function window_config()
    local columns = reader_columns()
    local width = math.max(1, math.min(data.width, columns - 4))
    return { relative = "editor", row = math.min(2, math.max(0, vim.o.lines - 4)),
      col = math.max(0, math.floor((columns - width - side) / 2)), width = width,
      height = math.max(1, vim.o.lines - 6), style = "minimal", border = "none", zindex = 20 }
  end
  local window = api.nvim_open_win(buffer, true, window_config())

  -- The status line says where the cursor is in the book and how it is read:
  -- the section's breadcrumb and page on the left, mode and progress on the
  -- right, then the two keys a reader needs to find everything else.
  local titles = {}
  for _, node in ipairs(type(data.structure) == "table" and data.structure.nodes or {}) do
    titles[node.key] = node.title
  end
  local function breadcrumb(path)
    local parts, key = {}, ""
    for segment in path:gmatch("[^/]+") do
      key = key .. "/" .. segment
      -- A chapter and its first section often share a title; say it once.
      if titles[key] and titles[key] ~= "" and titles[key] ~= parts[#parts] then parts[#parts + 1] = titles[key] end
    end
    return table.concat(parts, " › ")
  end
  local function pages(record)
    local first, last = record.context.printed_pages[1], record.context.printed_pages[2]
    if first == nil or first == vim.NIL then return "" end
    if last == nil or last == vim.NIL or last == first then return "p. " .. first end
    return "pp. " .. first .. "–" .. last
  end
  local function statusline_text()
    if not api.nvim_win_is_valid(window) then return "" end
    local row = api.nvim_win_get_cursor(window)[1]
    local record, index = records[1], 1
    for at, candidate in ipairs(records) do
      local position = positions[candidate.id]
      if position and position.first_row <= row then record, index = candidate, at end
    end
    local where = breadcrumb(record.context.path)
    local page = pages(record)
    local left = where ~= "" and (page ~= "" and where .. " · " .. page or where) or page
    local right = { mode == "paragraph" and "One paragraph" or "Continuous" }
    if data.focus then right[#right + 1] = "focus" end
    if data.progress ~= nil then
      local done = (data.progress.first + index - 1) / math.max(1, data.progress.total - 1)
      right[#right + 1] = string.format("%d%%", math.floor(100 * done + 0.5))
    end
    right[#right + 1] = "? keys · :q quit"
    right = table.concat(right, " · ")
    -- Keep at least three spaces between the halves: when they do not fit, the
    -- section path gives way from its start, so the page stays in view.
    local room = vim.o.columns - 2 - vim.fn.strdisplaywidth(right) - 3
    if vim.fn.strdisplaywidth(left) > room then
      local chars = vim.fn.strchars(left)
      local cut = 0
      while cut < chars and vim.fn.strdisplaywidth("…" .. vim.fn.strcharpart(left, cut)) > room do cut = cut + 1 end
      left = room > 1 and ("…" .. vim.fn.strcharpart(left, cut)) or ""
    end
    local function escape(text) return (text:gsub("%%", "%%%%")) end
    return " " .. escape(left) .. "%=   " .. escape(right) .. " "
  end
  _G.SOLStatus = function()
    local ok, text = pcall(statusline_text)
    return ok and text or " SOL"
  end
  api.nvim_create_autocmd("CursorMoved", { buffer = buffer, callback = function() vim.cmd("redrawstatus") end })
  vim.wo[window].wrap, vim.wo[window].linebreak, vim.wo[window].breakindent = true, true, false
  vim.wo[window].number, vim.wo[window].relativenumber, vim.wo[window].cursorline = false, false, false
  vim.wo[window].signcolumn, vim.wo[window].foldcolumn, vim.wo[window].colorcolumn = "no", "0", ""
  vim.wo[window].conceallevel, vim.wo[window].scrolloff, vim.wo[window].sidescrolloff = 0, 2, 0
  vim.wo[window].virtualedit, vim.wo[window].list, vim.wo[window].spell = "onemore", false, false
  -- The reading float is the page itself, not a box drawn on another surface.
  vim.wo[window].winhighlight = "NormalFloat:Normal"

  local function source_location(row, byte)
    if not integer(row) or not source_rows[row] then fail("endpoint is outside selectable source prose") end
    local item = source_rows[row]
    return { id = item.id, offset = item.start + byte_to_codepoint(item.text, byte) }
  end
  local function source_point(id, cp)
    local record, position = by_id[id], positions[id]
    if not record or not position or not integer(cp) or cp < 0 or cp > record._length then fail("position is outside the visible source") end
    for _, item in ipairs(position.rows) do
      if cp >= item.start and cp <= item.finish then
        return { row = item.row, byte = codepoint_to_byte(item.text, cp - item.start) }
      end
    end
    fail("source position has no exact buffer point")
  end
  local function verified_projection()
    if not api.nvim_buf_is_valid(buffer) or not vim.deep_equal(api.nvim_buf_get_lines(buffer, 0, -1, false), projection) then
      fail("displayed buffer disagrees with source; export refused")
    end
    if not vim.deep_equal(records, frozen_records) then fail("exported source metadata changed; export refused") end
  end
  local function point(value)
    if type(value) ~= "table" or not integer(value.row) or not integer(value.byte) then fail("invalid buffer endpoint") end
    return source_location(value.row, value.byte)
  end
  local function native_cursor()
    local value = api.nvim_win_get_cursor(window)
    return { row = value[1], byte = value[2] }
  end

  local function validate_packet(packet)
    if not exact_keys(packet, { "reference", "selection", "cursor_offset" }) then fail("invalid research packet shape") end
    local binding = type(packet.reference) == "table" and packet.reference.reference
    local record = type(binding) == "table" and by_id[binding.target_id]
    if not record or not vim.deep_equal(packet.reference, record.reference) then
      fail("packet does not bind this sampled corpus generation and record")
    end
    local cursor = packet.cursor_offset
    if not integer(cursor) or cursor < 0 or cursor > record._length then fail("invalid semantic cursor") end
    local selected = packet.selection
    if selected == vim.NIL then return record end
    if not exact_keys(selected, { "requested_id", "target_id", "start", "end", "text", "content_sha256", "plain_text_sha256" })
      or selected.requested_id ~= binding.requested_id or selected.target_id ~= binding.target_id
      or selected.content_sha256 ~= binding.content_sha256 or selected.plain_text_sha256 ~= record.plain_text_sha256
      or not integer(selected.start) or not integer(selected["end"])
      or selected.start < 0 or selected.start >= selected["end"] or selected["end"] > record._length
      or slice(record.plain_text, selected.start, selected["end"]) ~= selected.text
      or (cursor ~= selected.start and cursor ~= selected["end"]) then
      fail("selection identity, exact text, or codepoint boundaries disagree")
    end
    return record
  end

  local function capture(mode, anchor, cursor)
    verified_projection()
    mode = mode or vim.fn.mode(1)
    cursor = cursor or native_cursor()
    local focus = point(cursor)
    local record, selection, offset = by_id[focus.id], vim.NIL, focus.offset
    if mode == "v" then
      if not anchor then
        local value = vim.fn.getpos("v")
        anchor = { row = value[2], byte = value[3] - 1 }
      end
      local origin = point(anchor)
      if origin.id ~= focus.id then fail("selections across passages are not supported by this experiment") end
      local start = math.min(origin.offset, focus.offset)
      local finish = math.min(record._length, math.max(origin.offset, focus.offset) + 1)
      if start >= finish then fail("select a nonempty source span") end
      selection = { requested_id = record.reference.reference.requested_id,
        target_id = record.id, start = start, ["end"] = finish, text = slice(record.plain_text, start, finish),
        content_sha256 = record.reference.reference.content_sha256, plain_text_sha256 = record.plain_text_sha256 }
      offset = focus.offset < origin.offset and start or finish
    elseif mode ~= "n" then
      fail("only a normal cursor or characterwise visual selection can be exported")
    end
    local packet = { reference = vim.deepcopy(record.reference), selection = selection, cursor_offset = offset }
    validate_packet(packet)
    return packet
  end

  local function set_exact_cursor(cp)
    api.nvim_win_set_cursor(window, { cp.row, cp.byte })
    local actual = api.nvim_win_get_cursor(window)
    if actual[1] ~= cp.row or actual[2] ~= cp.byte then
      fail("Neovim cannot represent this exact scalar boundary; position was not adjusted")
    end
  end
  local function normal_escape()
    api.nvim_feedkeys(api.nvim_replace_termcodes("<Esc>", true, false, true), "nx", false)
  end
  local function restore(packet)
    verified_projection()
    local record = validate_packet(packet)
    api.nvim_set_current_win(window)
    normal_escape()
    if packet.selection == vim.NIL then
      set_exact_cursor(source_point(record.id, packet.cursor_offset))
    else
      local span = packet.selection
      local first, last = span.start, span["end"] - 1
      if packet.cursor_offset == span.start then first, last = last, first end
      set_exact_cursor(source_point(record.id, first))
      vim.cmd("normal! v")
      set_exact_cursor(source_point(record.id, last))
      local recovered = capture("v", source_point(record.id, first), source_point(record.id, last))
      if not vim.deep_equal(packet, recovered) then
        normal_escape(); fail("selection cannot be represented without changing its source endpoints")
      end
    end
    vim.cmd("normal! zz")
    return record.id
  end

  local function export(action)
    local packet = capture()
    local result = integrated and { action = action or "quit", packet = packet } or packet
    local encoded = vim.json.encode(result)
    local output, problem = uv.fs_open(output_path, "wx", 384) -- exclusive owner-only file, never overwrite
    if not output then fail("cannot create private result: " .. tostring(problem)) end
    local at = 0
    while at < #encoded do
      local written, write_problem = uv.fs_write(output, encoded:sub(at + 1), at)
      if not written or written == 0 then
        uv.fs_close(output); fail("could not finish result: " .. tostring(write_problem))
      end
      at = at + written
    end
    local closed, close_problem = uv.fs_close(output)
    if not closed then fail("could not close result: " .. tostring(close_problem)) end
    return packet
  end

  -- Semantic spans map once from source codepoints to UTF-8 extmark boundaries.
  -- Styling never enters canonical strings. Unknown/basic terminals underline em.
  local italic_capable = data.emphasis == "italic"
  -- Terminal restores the host's own background setting; colored presets declare theirs.
  if rawget(_G, 'SOLInitialBackground') == nil then _G.SOLInitialBackground = vim.o.background end
  local function apply_theme()
    if not data.theme then
      api.nvim_set_hl(0, "SOLSourceHeading", { bold = true })
      api.nvim_set_hl(0, "SOLSourceWarning", { link = "WarningMsg" })
      return
    end
    local active = data.theme.active
    local declared = presets[active].background
    local background = declared ~= "" and declared or _G.SOLInitialBackground
    vim.o.termguicolors = active ~= "terminal" and data.theme.truecolor
    -- Changing 'background' resets Neovim's default groups, so it precedes ours.
    if vim.o.background ~= background then vim.o.background = background end
    for name in pairs(theme_groups) do api.nvim_set_hl(0, name, vim.deepcopy(presets[active].groups[name] or {})) end
  end
  apply_theme()
  local function semantic_group(styles)
    local enabled, names = {}, {}
    for _, name in ipairs(styles) do enabled[name], names[#names + 1] = true, name end
    table.sort(names)
    local group = "SOLSemantic_" .. table.concat(names, "_")
    api.nvim_set_hl(0, group, { italic = enabled.emphasis and not not italic_capable or false,
      underline = (enabled.emphasis and not italic_capable) or enabled.code or false,
      bold = enabled.strong or enabled.heading or false })
    return group
  end
  for _, row in ipairs(heading_rows) do
    api.nvim_buf_set_extmark(buffer, namespace, row - 1, 0,
      { end_row = row - 1, end_col = #projection[row], hl_group = "SOLSourceHeading" })
  end
  for _, row in ipairs(warning_rows) do
    api.nvim_buf_set_extmark(buffer, namespace, row - 1, 0,
      { end_row = row - 1, end_col = #projection[row], hl_group = "SOLSourceWarning" })
  end
  for _, record in ipairs(records) do
    if positions[record.id] then
      for _, span in ipairs(record.styles) do
        local group = semantic_group(span.styles)
        local first, last = source_point(record.id, span.start), source_point(record.id, span["end"])
        api.nvim_buf_set_extmark(buffer, namespace, first.row - 1, first.byte,
          { end_row = last.row - 1, end_col = last.byte, hl_group = group, priority = 100 })
        style_runs[#style_runs + 1] = { id = record.id, start = span.start, ["end"] = span["end"], group = group }
      end
    end
  end
  -- After a search jump, the opened passage's verified matches are marked;
  -- Esc hides them. Marks are display only, like the search itself.
  local search_namespace = api.nvim_create_namespace("sol-search-marks")
  if data.search_marks ~= nil and data.search_marks ~= vim.NIL then
    local marks = data.search_marks
    if type(marks) ~= "table" or type(marks.id) ~= "string" or type(marks.spans) ~= "table" then
      fail("invalid search marks")
    end
    local record = by_id[marks.id]
    for _, span in ipairs(marks.spans) do
      if not record or type(span) ~= "table" or not integer(span[1]) or not integer(span[2])
        or span[1] < 0 or span[1] >= span[2] or span[2] > record._length then fail("invalid search mark") end
    end
    if record and positions[record.id] then
      for _, span in ipairs(marks.spans) do
        local first, last = source_point(record.id, span[1]), source_point(record.id, span[2])
        api.nvim_buf_set_extmark(buffer, search_namespace, first.row - 1, first.byte,
          { end_row = last.row - 1, end_col = last.byte, hl_group = "Search", priority = 150 })
      end
    end
  end
  -- Footnote callouts are hidden from the source text; each is shown where
  -- the canonical Markdown places it, as inline display text only.
  local superscript = { ["0"] = "⁰", ["1"] = "¹", ["2"] = "²", ["3"] = "³", ["4"] = "⁴",
    ["5"] = "⁵", ["6"] = "⁶", ["7"] = "⁷", ["8"] = "⁸", ["9"] = "⁹" }
  for _, record in ipairs(records) do
    if positions[record.id] then
      for _, callout in ipairs(record.callouts) do
        local mark = callout.label:match("^%d+$") and callout.label:gsub("%d", superscript) or "[" .. callout.label .. "]"
        local point = source_point(record.id, callout.offset)
        api.nvim_buf_set_extmark(buffer, namespace, point.row - 1, point.byte,
          { virt_text = { { mark, "NonText" } }, virt_text_pos = "inline", right_gravity = false })
      end
    end
  end

  local function cycle_theme()
    if not data.theme then fail('themes need the installed SOL reader') end
    local at = 1
    for index, name in ipairs(theme_order) do if name == data.theme.active then at = index end end
    data.theme.active = theme_order[at % #theme_order + 1]
    apply_theme()
    local essence = rawget(_G, 'SOLEssence')
    if essence and essence.set_theme then essence.set_theme(data.theme.active) end
    local preset = presets[data.theme.active]
    local message = preset.notice ~= '' and preset.notice or ('Theme: ' .. preset.label ..
      ' for this session. Keep it with: sol --set-theme ' .. preset.name)
    api.nvim_echo({{message, 'None'}}, false, {})
    return data.theme.active
  end

  return {
    data = data,
    integrated = integrated,
    mode = mode,
    focused_id = focused_id,
    records = records,
    by_id = by_id,
    positions = positions,
    source_rows = source_rows,
    namespace = namespace,
    projection = projection,
    style_runs = style_runs,
    buffer = buffer,
    window = window,
    source_location = source_location,
    source_point = source_point,
    verified_projection = verified_projection,
    native_cursor = native_cursor,
    validate_packet = validate_packet,
    capture = capture,
    set_exact_cursor = set_exact_cursor,
    normal_escape = normal_escape,
    restore = restore,
    export = export,
    apply_theme = apply_theme,
    semantic_group = semantic_group,
    search_namespace = search_namespace,
    superscript = superscript,
    window_config = window_config,
    reader_columns = reader_columns,
    set_side = function(columns)
      side = columns
      if api.nvim_win_is_valid(window) then api.nvim_win_set_config(window, window_config()) end
    end,
    breadcrumb = breadcrumb,
    pages = pages,
    cycle_theme = cycle_theme,
  }
end
