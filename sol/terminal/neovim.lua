-- Native SOL reading surface. Source strings are data, never Ex/Lua code.
-- Python owns corpus verification and validates the returned research packet.
local supplied = ...
local api, uv = vim.api, vim.uv or vim.loop
for _, server in ipairs(vim.fn.serverlist()) do pcall(vim.fn.serverstop, server) end

local function fail(message) error("SOL reader: " .. message, 0) end
local function integer(value) return type(value) == "number" and value == math.floor(value) end
local function exact_keys(value, names)
  if type(value) ~= "table" then return false end
  local allowed, count = {}, 0
  for _, name in ipairs(names) do allowed[name] = true end
  for name in pairs(value) do
    if not allowed[name] then return false end
    count = count + 1
  end
  return count == #names
end

-- Unlike display cells, these boundaries include every Unicode scalar, including
-- combining marks. Refuse malformed UTF-8 and byte-interior positions outright.
local function boundaries(text)
  if type(text) ~= "string" then fail("source text is not a string") end
  local result, reverse, byte, cp = { 0 }, { [0] = 0 }, 1, 0
  while byte <= #text do
    local first, size, scalar = text:byte(byte), 1, 0
    if first < 0x80 then scalar = first
    elseif first >= 0xC2 and first <= 0xDF then size, scalar = 2, first - 0xC0
    elseif first >= 0xE0 and first <= 0xEF then size, scalar = 3, first - 0xE0
    elseif first >= 0xF0 and first <= 0xF4 then size, scalar = 4, first - 0xF0
    else fail("source contains malformed UTF-8") end
    for index = byte + 1, byte + size - 1 do
      local continuation = text:byte(index)
      if not continuation or continuation < 0x80 or continuation > 0xBF then
        fail("source contains malformed UTF-8")
      end
      scalar = scalar * 64 + continuation - 0x80
    end
    if (size == 2 and scalar < 0x80) or (size == 3 and scalar < 0x800)
      or (size == 4 and scalar < 0x10000) or scalar > 0x10FFFF
      or (scalar >= 0xD800 and scalar <= 0xDFFF) then fail("source contains invalid Unicode scalars") end
    if scalar == 0 or scalar == 13 or scalar == 127 or (scalar < 32 and scalar ~= 9 and scalar ~= 10) then
      fail("source contains unsupported control characters; source was not changed")
    end
    byte, cp = byte + size, cp + 1
    result[cp + 1], reverse[byte - 1] = byte - 1, cp
  end
  return result, reverse
end

local function byte_to_codepoint(text, byte)
  local _, reverse = boundaries(text)
  if not integer(byte) or reverse[byte] == nil then fail("endpoint is not an exact UTF-8 boundary") end
  return reverse[byte]
end
local function codepoint_to_byte(text, cp)
  local points = boundaries(text)
  if not integer(cp) or cp < 0 or cp >= #points then fail("source codepoint is outside the passage") end
  return points[cp + 1]
end
local function slice(text, start, finish)
  return text:sub(codepoint_to_byte(text, start) + 1, codepoint_to_byte(text, finish))
end

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
    if not exact_keys(preset, { "name", "label", "groups", "notice" }) or type(preset.name) ~= "string"
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
local known_styles = { emphasis = true, strong = true, code = true, quotation = true, heading = true }
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
local function valid_styles(styles, length)
  if type(styles) ~= "table" then fail("missing semantic style spans") end
  for _, span in ipairs(styles) do
    if type(span) ~= "table" or not integer(span.start) or not integer(span["end"])
      or span.start < 0 or span.start >= span["end"] or span["end"] > length
      or type(span.styles) ~= "table" or #span.styles == 0 then fail("invalid semantic style span") end
    for _, name in ipairs(span.styles) do
      if not known_styles[name] then fail("unknown semantic style") end
    end
  end
end
local function valid_strings(values)
  if type(values) ~= "table" then fail("invalid source warnings") end
  for _, value in ipairs(values) do boundaries(value) end
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
-- No "~" past the text and no "@@@" when a paragraph continues below the window.
vim.o.fillchars = "eob: ,lastline: "
vim.o.statusline = " j/k lines   [p/]p passages   / search   v select   c source/notes   ? help   q return"
if integrated then
  vim.o.statusline = " SOL " .. mode .. " | b/n paragraphs  p mode  m1-3 mark  y copy  t tree  ? help  q quit"
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

local function window_config()
  local width = math.max(1, math.min(data.width, vim.o.columns - 4))
  return { relative = "editor", row = math.min(2, math.max(0, vim.o.lines - 4)),
    col = math.max(0, math.floor((vim.o.columns - width) / 2)), width = width,
    height = math.max(1, vim.o.lines - 6), style = "minimal", border = "none", zindex = 20 }
end
local window = api.nvim_open_win(buffer, true, window_config())
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
-- Terminal restores the host's own background setting; Dark/Paper declare theirs.
if rawget(_G, 'SOLInitialBackground') == nil then _G.SOLInitialBackground = vim.o.background end
local function apply_theme()
  if not data.theme then
    api.nvim_set_hl(0, "SOLSourceHeading", { bold = true })
    api.nvim_set_hl(0, "SOLSourceWarning", { link = "WarningMsg" })
    return
  end
  local active = data.theme.active
  local background = active == "paper" and "light" or active == "dark" and "dark" or _G.SOLInitialBackground
  vim.o.termguicolors = active ~= "terminal" and data.theme.truecolor
  -- Changing 'background' resets Neovim's default groups, so it precedes ours.
  if vim.o.background ~= background then vim.o.background = background end
  for name in pairs(theme_groups) do api.nvim_set_hl(0, name, vim.deepcopy(presets[active].groups[name] or {})) end
end
apply_theme()
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
      local enabled, names = {}, {}
      for _, name in ipairs(span.styles) do enabled[name], names[#names + 1] = true, name end
      table.sort(names)
      local group = "SOLSemantic_" .. table.concat(names, "_")
      api.nvim_set_hl(0, group, { italic = enabled.emphasis and not not italic_capable or false,
        underline = (enabled.emphasis and not italic_capable) or enabled.code or false,
        bold = enabled.strong or enabled.heading or false })
      local first, last = source_point(record.id, span.start), source_point(record.id, span["end"])
      api.nvim_buf_set_extmark(buffer, namespace, first.row - 1, first.byte,
        { end_row = last.row - 1, end_col = last.byte, hl_group = group, priority = 100 })
      style_runs[#style_runs + 1] = { id = record.id, start = span.start, ["end"] = span["end"], group = group }
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

local popup, popup_context = nil, false
local function close_popup()
  if popup and api.nvim_win_is_valid(popup) then api.nvim_win_close(popup, true) end
  popup = nil
  popup_context = false
  if api.nvim_win_is_valid(window) then api.nvim_set_current_win(window) end
end
local function show_lines(lines)
  close_popup()
  local panel = api.nvim_create_buf(false, true)
  api.nvim_buf_set_lines(panel, 0, -1, false, lines)
  vim.bo[panel].modifiable, vim.bo[panel].readonly, vim.bo[panel].bufhidden = false, true, "wipe"
  local width, height = math.max(1, math.min(data.width, vim.o.columns - 6)), math.max(1, vim.o.lines - 8)
  popup = api.nvim_open_win(panel, true, { relative = "editor", row = 3,
    col = math.max(0, math.floor((vim.o.columns - width) / 2)), width = width,
    height = math.min(height, math.max(1, #lines)), style = "minimal", border = "single", zindex = 50 })
  vim.wo[popup].wrap, vim.wo[popup].linebreak = true, true
  vim.wo[popup].winhighlight = "NormalFloat:SOLPanel,FloatBorder:SOLPanelBorder"
  for _, key in ipairs({ "<Esc>", "q", "c" }) do
    vim.keymap.set("n", key, close_popup, { buffer = panel, silent = true })
  end
  vim.keymap.set("n", "j", "gj", { buffer = panel, silent = true })
  vim.keymap.set("n", "k", "gk", { buffer = panel, silent = true })
end
local function current_packet()
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
local function reload(payload)
  return assert(loadfile(vim.env.SOL_NVIM_ADAPTER))(payload)
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
local show_search, show_source
local function request(operation, fields, callback)
  if not channel then fail('this action needs the installed SOL reader, not a research export') end
  if channel.navigation_pending then return end
  local message = vim.deepcopy(fields or {})
  channel.serial = channel.serial + 1
  message.id, message.op, message.packet, message.mode = channel.serial, operation, current_packet(), mode
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
      elseif result.search then show_search(result.search)
      elseif result.source then show_source(result.source)
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
show_search = function(result)
  local lines = {'Search: ' .. result.query, 'Whole book, literal and case-insensitive. Up to ' .. result.limit .. ' passages.', ''}
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
  if #result.rows > 0 then api.nvim_win_set_cursor(popup, {4, 0}) end
  vim.keymap.set('n', '<CR>', function()
    local number = rows[api.nvim_win_get_cursor(popup)[1]]
    if not number then return end
    close_popup(); request('search_open', {result = number})
  end, {buffer = panel, silent = true})
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
  lines[#lines + 1] = (#result.pages > 1 and 'A page number shows that page. ' or '') .. 'Esc returns to reading.'
  show_lines(lines)
  local panel = api.nvim_get_current_buf()
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
-- A personal note binds the whole passage through the workspace service. A
-- selection is shown as context above the editor and is not stored. Drafts
-- survive any close except an explicit discard, and an unacknowledged save.
local note_namespace = api.nvim_create_namespace('sol-note')
local function note()
  if not data.personal then fail('notes need the installed SOL reader') end
  if not data.personal.persistent then fail('notes need a workspace; this temporary -n session saves nothing') end
  local packet = current_packet()
  local record = by_id[packet.reference.reference.target_id]
  if vim.fn.mode(1) ~= 'n' then normal_escape() end
  close_popup()
  local channel_state = rawget(_G, 'SOLReaderChannel')
  local drafts = channel_state and channel_state.drafts or {}
  if channel_state then channel_state.drafts = drafts end
  local editor = api.nvim_create_buf(false, true)
  vim.bo[editor].buftype, vim.bo[editor].bufhidden = 'acwrite', 'wipe'
  api.nvim_buf_set_name(editor, 'sol://note/' .. record.id .. '/' .. editor)
  if drafts[record.id] then
    api.nvim_buf_set_lines(editor, 0, -1, false, vim.split(drafts[record.id], '\n', { plain = true }))
  end
  vim.bo[editor].modified = false
  local width = math.max(20, math.min(data.width, vim.o.columns - 6))
  local quote = {}
  if packet.selection ~= vim.NIL then
    local text, line = packet.selection.text:gsub('%s+', ' '), ''
    for _, char in ipairs(vim.fn.split(text, '\zs')) do
      if vim.fn.strdisplaywidth(line .. char) > width - 2 then
        quote[#quote + 1] = line; line = ''
        if #quote == 3 then quote[3] = vim.fn.strcharpart(quote[3], 0, vim.fn.strchars(quote[3]) - 1) .. '…'; break end
      end
      line = line .. char
    end
    if #quote < 3 and line ~= '' then quote[#quote + 1] = line end
  end
  popup = api.nvim_open_win(editor, true, { relative = 'editor', row = 3,
    col = math.max(0, math.floor((vim.o.columns - width) / 2)), width = width,
    height = math.max(3, math.min(12 + #quote, vim.o.lines - 10)), style = 'minimal', border = 'single', zindex = 50,
    title = ' Note on: ' .. vim.fn.strcharpart(record.heading, 0, width - 14) .. ' ', title_pos = 'left',
    footer = ' Ctrl-S or :w saves · Ctrl-C discards ', footer_pos = 'right' })
  vim.wo[popup].wrap, vim.wo[popup].linebreak = true, true
  vim.wo[popup].winhighlight = 'NormalFloat:SOLPanel,FloatBorder:SOLPanelBorder'
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
    if not finished and body():match('%S') then
      drafts[record.id] = body()
      vim.schedule(function() api.nvim_echo({ { 'Note draft kept; press a on this passage to continue it', 'WarningMsg' } }, false, {}) end)
    end
  end })
  local function save()
    local text = body()
    if not text:match('%S') then fail('empty note; nothing saved') end
    -- Keep the draft until Python acknowledges the save.
    drafts[record.id], finished = text, true
    vim.cmd('stopinsert')
    close_popup()
    restore(packet)
    request('note_add', { body = text }, function()
      drafts[record.id] = nil
      api.nvim_echo({ { 'Note saved in your workspace', 'None' } }, false, {})
    end)
  end
  local function discard()
    drafts[record.id], finished = nil, true
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
local function search()
  -- Standard command-line input works in any Neovim-capable terminal. A cancelled
  -- query never visits a result or modifies canonical text/selection.
  local query = vim.fn.input('Search book: ')
  if query:match('%S') then request('search', {query = query}) end
end
local function marker(slot, operation)
  request(operation or 'marker_set', {slot = slot})
end
local function yank()
  local packet = current_packet()
  local record = by_id[packet.reference.reference.target_id]
  local text = packet.selection ~= vim.NIL and packet.selection.text or record.plain_text
  vim.fn.setreg('"', text, 'v')
  if vim.fn.has('clipboard') ~= 1 then
    fail('No system clipboard provider. Text is in the Neovim register only; install wl-clipboard (Wayland) or xclip (X11).')
  end
  if vim.fn.setreg('+', text, 'v') ~= 0 then fail('clipboard provider refused the yank') end
  normal_escape()
  api.nvim_echo({{'Copied to clipboard', 'None'}}, false, {})
  return text
end
local tree_view
local function tree()
  if not data.structure then fail('tree navigation needs the installed SOL reader') end
  close_popup()
  local packet = current_packet()
  local record = by_id[packet.reference.reference.target_id]
  local structure = vim.deepcopy(data.structure)
  structure.current = record.context.path
  local implementation = assert(loadfile(vim.fn.fnamemodify(vim.env.SOL_NVIM_ADAPTER, ':h') .. '/neovim_tree.lua'))()
  tree_view = implementation.open(structure, {
    choose = function(key) request('node_open', {node = key}) end,
    close = function()
      tree_view = nil
      if api.nvim_win_is_valid(window) then api.nvim_set_current_win(window) end
      if data.tree_only then current_packet(); export('quit'); vim.cmd('qa!') end
    end,
  })
  return tree_view
end
local function context()
  local packet = current_packet()
  local record = by_id[packet.reference.reference.target_id]
  local lines = { record.heading, "", "Source context (not selectable passage text)", "" }
  local function add(text)
    for _, line in ipairs(vim.split(tostring(text), "\n", { plain = true })) do lines[#lines + 1] = line end
  end
  add(record.context.path)
  add('Reading scope: loaded section (' .. #records .. ' paragraphs); gg/G stay here.')
  add("Printed pages: " .. vim.json.encode(record.context.printed_pages))
  add("PDF pages: " .. vim.json.encode(record.context.pdf_pages))
  add("Attribution: " .. vim.json.encode(record.context.attribution))
  add("Record: " .. record.id)
  if data.markers then
    add(''); add('Paragraph markers' .. (data.markers.persistent and ' (saved in workspace)' or ' (temporary session only)'))
    for _, slot in ipairs(data.markers.slots) do
      add(tostring(slot.slot) .. '. ' .. slot.label .. (slot.resolved == record.id and '  [here]' or ''))
    end
    add("m1/m2/m3 place; '1/'2/'3 return; dm1/dm2/dm3 clear")
  end
  for _, warning in ipairs(record.warnings) do add("Warning: " .. warning) end
  if #record.notes > 0 then add(""); add("Footnotes on this passage (" .. #record.notes .. ")") end
  for _, note in ipairs(record.notes) do
    local author = note.attribution.author
    add(""); add("[" .. (note.label ~= "" and note.label or "?") .. "] " .. tostring(note.attribution.role)
      .. ", " .. tostring(note.attribution.status) .. (type(author) == "string" and ", " .. author or ""))
    for _, warning in ipairs(note.warnings) do add("Warning: " .. warning) end
    add(note.plain_text)
  end
  if data.personal then
    add("")
    if not data.personal.persistent then
      add("Personal notes need a workspace; this temporary session saves nothing.")
    else
      local mine = data.personal.notes[record.id] or {}
      add("Your workspace notes on this passage (" .. #mine .. "); a adds one")
      for _, item in ipairs(mine) do
        add("— " .. item.author .. ", " .. item.created_at)
        for _, line in ipairs(item.lines) do add(line) end
      end
    end
  end
  add(""); add("Esc returns to reading. Notes and context have no passage-selection identity.")
  show_lines(lines)
  popup_context = true
  if data.markers then
    for slot = 1, 3 do
      local number = slot
      vim.keymap.set('n', tostring(number), function() request('marker_open', {slot = number}) end,
        {buffer = api.nvim_get_current_buf(), silent = true})
    end
  end
end
local function cycle_theme()
  if not data.theme then fail('themes need the installed SOL reader') end
  local at = 1
  for index, name in ipairs(theme_order) do if name == data.theme.active then at = index end end
  data.theme.active = theme_order[at % #theme_order + 1]
  apply_theme()
  local preset = presets[data.theme.active]
  local message = preset.notice ~= '' and preset.notice or ('Theme: ' .. preset.label ..
    ' for this session. Keep it with: sol --set-theme ' .. preset.name)
  api.nvim_echo({{message, 'None'}}, false, {})
  return data.theme.active
end
local function help()
  if integrated then
    show_lines({ "SOL reader (" .. mode .. ")", "",
      "j/k, Ctrl-d/u    wrapped reading lines / half-window scroll",
      "h/l, w           character / forward word motions",
      "gg/G             start / end of this loaded reading section",
      "b / n            previous / next paragraph",
      "p                toggle continuous / one-paragraph reading",
      "m1, m2, m3       attach/move one of three paragraph markers",
      "'1, '2, '3       jump to a marker; dm1/dm2/dm3 clear it",
      "y                copy the selection or current paragraph to clipboard",
      "t                book outline: h/l branches, Enter read, Esc return",
      "/                literal search across the whole book",
      "Ctrl-P / Ctrl-N  previous / next search-result passage",
      "Alt-Left/Right   return / forward through reading history",
      "v                characterwise selection inside one passage",
      "c                source pages, attribution and linked notes",
      "s                show the printed source of this passage (formulas)",
      "a                write a personal note on this passage (workspace)",
      "f                toggle quiet focus mode",
      "T                cycle Terminal / Dark / Paper theme for this session",
      "q / Ctrl-q       save the semantic position and quit",
      ":qa!             quit without saving the current cursor", "",
      "In paragraph mode, j/k stay here. Use b/n to change paragraph.",
      "In continuous mode, j/k can continue across reading sections.",
      "Selections are transient; no annotation is created automatically.",
      "Canonical text is read-only. Personal Neovim configuration is not loaded.",
      "Esc closes this help." })
    return
  end
  show_lines({ "Reader experiment — not a workspace editor", "",
    "j/k           visual wrapped rows; h/l retain Neovim character motions",
    "Ctrl-d/u      Neovim half-window scroll; gg/G the bounded sample",
    "[p / ]p       previous / next source passage",
    "/, n, N       native Neovim search and matches",
    "v             characterwise visual selection inside one passage",
    "c             edition/page context and attributed source notes",
    "q / Ctrl-q    export exact position/selection, then return",
    ":SOLExport    export without quitting (output must not already exist)",
    ":qa!          quit without exporting; no workspace is modified", "",
    "Linewise/blockwise/cross-passage selections cannot be exported.",
    "A selection exports Unicode codepoint boundaries, never display cells.",
    "Rendering is read-only, not a security sandbox. Personal config is not loaded.",
    "Esc closes this help." })
end
local function guarded(fn)
  return function()
    local ok, result = pcall(fn)
    if not ok then vim.notify(tostring(result), vim.log.levels.ERROR) end
    return ok, result
  end
end
local function reading_request(action)
  if action ~= "quit" then
    if not integrated or not data.navigation[action] then return end
    if vim.fn.mode(1) ~= "n" then fail("clear selection before changing reading sections") end
    if channel then request(action); return end
  end
  if channel and next(channel.pending) then
    if not vim.wait(2500, function() return next(channel.pending) == nil end, 10) then
      fail('waiting for a marker/navigation save; retry quitting after it is acknowledged')
    end
    if not api.nvim_buf_is_valid(buffer) then return _G.SOLNvimReader.quit() end
  end
  -- Metadata is not prose identity. In normal mode only, a quit/section request
  -- on a heading or separator explicitly lands on the closest actual source row.
  -- Visual endpoints remain strict and are never silently adjusted.
  local cursor = native_cursor()
  if integrated and vim.fn.mode(1) == "n" and not source_rows[cursor.row] then
    local nearest, distance
    for row, item in pairs(source_rows) do
      local delta = math.abs(row - cursor.row)
      if not distance or delta < distance or (delta == distance and row < nearest.row) then
        nearest, distance = item, delta
      end
    end
    local offset = cursor.row > nearest.row and nearest.finish or nearest.start
    set_exact_cursor(source_point(nearest.id, offset))
  end
  export(action)
  vim.cmd("qa!")
end
local function passage(delta)
  local packet = current_packet()
  local selected
  for index, record in ipairs(records) do
    if record.id == packet.reference.reference.target_id then selected = records[index + delta]; break end
  end
  if selected then
    if mode == 'paragraph' then
      local payload = vim.deepcopy(data)
      payload.restore = {reference = vim.deepcopy(selected.reference), selection = vim.NIL, cursor_offset = 0}
      payload.mode, payload.tree_only = mode, false
      reload(payload)
    else set_exact_cursor(source_point(selected.id, 0)); vim.cmd('normal! zt') end
  elseif integrated then request(delta > 0 and 'passage_next' or 'passage_previous') end
end
for _, key in ipairs({ "q", "<C-q>" }) do
  vim.keymap.set({ "n", "x" }, key, guarded(function() reading_request("quit") end), { buffer = buffer, silent = true })
end
vim.keymap.set({ "n", "x" }, "j", "gj", { buffer = buffer, silent = true })
vim.keymap.set({ "n", "x" }, "k", "gk", { buffer = buffer, silent = true })
if integrated then
  for key, motion in pairs({ j = "gj", k = "gk" }) do
    vim.keymap.set("n", key, guarded(function()
      local before = api.nvim_win_get_cursor(window)
      vim.cmd("normal! " .. motion)
      local after = api.nvim_win_get_cursor(window)
      if mode == 'paragraph' then
        if not source_rows[after[1]] then
          local record = by_id[focused_id]
          set_exact_cursor(source_point(record.id, key == 'j' and record._length or 0))
        end
      else
        local edge = key == "j" and after[1] >= positions[records[#records].id].last_row
          or key == "k" and after[1] <= positions[records[1].id].first_row
        if edge and vim.deep_equal(before, after) then reading_request(key == "j" and "next" or "previous") end
      end
    end), { buffer = buffer, silent = true })
  end
  vim.keymap.set("n", "[c", guarded(function() reading_request("previous") end), { buffer = buffer, silent = true })
  vim.keymap.set("n", "]c", guarded(function() reading_request("next") end), { buffer = buffer, silent = true })
  vim.keymap.set({'n', 'x'}, 'p', guarded(toggle_mode), {buffer = buffer, silent = true})
  vim.keymap.set({'n', 'x'}, 'y', guarded(yank), {buffer = buffer, silent = true})
  vim.keymap.set('n', 't', guarded(tree), {buffer = buffer, silent = true})
  vim.keymap.set('n', 'f', guarded(toggle_focus), {buffer = buffer, silent = true})
  vim.keymap.set('n', 'b', guarded(function() passage(-1) end), {buffer = buffer, silent = true})
  vim.keymap.set('n', 'n', guarded(function() passage(1) end), {buffer = buffer, silent = true})
  vim.keymap.set('n', '/', guarded(search), {buffer = buffer, silent = true})
  vim.keymap.set('n', 's', guarded(source), {buffer = buffer, silent = true})
  vim.keymap.set({'n', 'x'}, 'a', guarded(note), {buffer = buffer, silent = true})
  vim.keymap.set('n', '<C-n>', guarded(function() request('search_next') end), {buffer = buffer, silent = true})
  vim.keymap.set('n', '<C-p>', guarded(function() request('search_previous') end), {buffer = buffer, silent = true})
  vim.keymap.set('n', '<M-Left>', guarded(function() request('history_back') end), {buffer = buffer, silent = true})
  vim.keymap.set('n', '<M-Right>', guarded(function() request('history_forward') end), {buffer = buffer, silent = true})
  for slot = 1, 3 do
    local number = slot
    vim.keymap.set('n', 'm' .. number, guarded(function() marker(number) end), {buffer = buffer, silent = true})
    vim.keymap.set('n', "'" .. number, guarded(function() marker(number, 'marker_open') end), {buffer = buffer, silent = true})
    vim.keymap.set('n', 'dm' .. number, guarded(function() marker(number, 'marker_clear') end), {buffer = buffer, silent = true})
  end
end
vim.keymap.set("n", "[p", guarded(function() passage(-1) end), { buffer = buffer, silent = true })
vim.keymap.set("n", "]p", guarded(function() passage(1) end), { buffer = buffer, silent = true })
vim.keymap.set("n", "c", guarded(context), { buffer = buffer, silent = true })
vim.keymap.set("n", "?", help, { buffer = buffer, silent = true })
if data.theme then vim.keymap.set("n", "T", guarded(cycle_theme), { buffer = buffer, silent = true }) end
if not integrated then api.nvim_create_user_command("SOLExport", guarded(function() export() end), {}) end
local group = api.nvim_create_augroup('SOLReaderView', {clear = true})
api.nvim_create_autocmd("VimResized", { group = group, callback = function()
  if tree_view then tree_view.resize() else close_popup() end
  if api.nvim_win_is_valid(window) then api.nvim_win_set_config(window, window_config()) end
end })
-- Terminal background detection can reset default groups after startup.
api.nvim_create_autocmd({ "ColorScheme", "OptionSet" }, { group = group, callback = function(event)
  if event.event == "OptionSet" and event.match ~= "background" then return end
  vim.schedule(function() if api.nvim_buf_is_valid(buffer) then apply_theme() end end)
end })

_G.SOLNvimReader = { records = records, buffer = buffer, window = window, positions = positions,
  source_rows = source_rows, namespace = namespace, styles = style_runs,
  source_location = source_location, source_point = source_point, capture = capture,
  restore = restore, export = export, validate_packet = validate_packet,
  byte_to_codepoint = byte_to_codepoint, codepoint_to_byte = codepoint_to_byte,
  verified_projection = verified_projection, context = context, help = help,
  toggle_mode = toggle_mode, mode = mode, yank = yank, tree = tree, marker = marker, source = source,
  cycle_theme = cycle_theme, theme = function() return data.theme and data.theme.active end,
  quit = function() reading_request('quit') end,
  marker_slots = function() return vim.deepcopy(data.markers) end,
  update_markers = function(markers)
    data.markers = markers
    if popup_context then context() end
  end,
  update_personal = function(personal)
    data.personal = personal
    if popup_context then context() end
  end,
  note = note,
  dispose = function()
    close_popup()
    if tree_view then tree_view.dispose() end
    if api.nvim_win_is_valid(window) then api.nvim_win_close(window, true) end
    if api.nvim_buf_is_valid(buffer) then api.nvim_buf_delete(buffer, {force = true}) end
  end }
if data.restore ~= nil and data.restore ~= vim.NIL then restore(data.restore)
else set_exact_cursor(source_point(records[1].id, 0)) end
if data.tree_only then tree() end
