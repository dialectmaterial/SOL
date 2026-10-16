-- Checkout-only reader experiment. Source strings are data, never Ex/Lua code.
-- Python owns corpus verification and validates the returned research packet.
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
local fd, read_error = uv.fs_open(input_path, "r", 0)
if not fd then fail("cannot read private input: " .. tostring(read_error)) end
local stat = uv.fs_fstat(fd)
if not stat or stat.type ~= "file" or stat.size > 16 * 1024 * 1024 then
  uv.fs_close(fd); fail("input must be a regular file smaller than 16 MiB")
end
local raw, read_problem = uv.fs_read(fd, stat.size, 0)
uv.fs_close(fd)
if not raw then fail("cannot read input: " .. tostring(read_problem)) end
local decoded, data = pcall(vim.json.decode, raw)
if not decoded or type(data) ~= "table" or type(data.records) ~= "table"
  or #data.records < 1 or #data.records > 64 then fail("invalid bounded source input") end
if not integer(data.width) or data.width < 8 or data.width > 1000 then fail("invalid reading width") end
if data.emphasis ~= nil and data.emphasis ~= "italic" and data.emphasis ~= "underline" then
  fail("invalid semantic emphasis presentation")
end

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
  if record.heading ~= previous_heading then
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
  for _, note in ipairs(record.notes) do
    if type(note) ~= "table" or type(note.attribution) ~= "table" then fail("invalid attributed note") end
    local note_length = #boundaries(note.plain_text) - 1
    valid_styles(note.styles, note_length)
    valid_strings(note.warnings)
  end
  append("")
end
local frozen_records = vim.deepcopy(records)

vim.o.modeline, vim.o.exrc = false, false
vim.o.swapfile, vim.o.backup, vim.o.writebackup, vim.o.undofile = false, false, false, false
vim.o.laststatus, vim.o.showtabline, vim.o.cmdheight = 3, 0, 1
vim.o.showmode, vim.o.showcmd, vim.o.ruler, vim.o.hidden = false, false, false, true
vim.o.mouse, vim.o.clipboard = "", ""
vim.o.statusline = " j/k lines   [p/]p passages   / search   v select   c source/notes   ? help   q return"
vim.o.selection = "inclusive"
vim.o.hlsearch = true
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

local function source_location(row, byte)
  if not integer(row) or not source_rows[row] then fail("endpoint is outside selectable source prose") end
  local item = source_rows[row]
  return { id = item.id, offset = item.start + byte_to_codepoint(item.text, byte) }
end
local function source_point(id, cp)
  local record, position = by_id[id], positions[id]
  if not record or not integer(cp) or cp < 0 or cp > record._length then fail("position is outside the sample") end
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

local function export()
  local packet = capture()
  local encoded = vim.json.encode(packet)
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
api.nvim_set_hl(0, "SOLSourceHeading", { bold = true })
api.nvim_set_hl(0, "SOLSourceWarning", { link = "WarningMsg" })
for _, row in ipairs(heading_rows) do
  api.nvim_buf_set_extmark(buffer, namespace, row - 1, 0,
    { end_row = row - 1, end_col = #projection[row], hl_group = "SOLSourceHeading" })
end
for _, row in ipairs(warning_rows) do
  api.nvim_buf_set_extmark(buffer, namespace, row - 1, 0,
    { end_row = row - 1, end_col = #projection[row], hl_group = "SOLSourceWarning" })
end
for _, record in ipairs(records) do
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

local popup
local function close_popup()
  if popup and api.nvim_win_is_valid(popup) then api.nvim_win_close(popup, true) end
  popup = nil
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
  for _, key in ipairs({ "<Esc>", "q", "c" }) do
    vim.keymap.set("n", key, close_popup, { buffer = panel, silent = true })
  end
  vim.keymap.set("n", "j", "gj", { buffer = panel, silent = true })
  vim.keymap.set("n", "k", "gk", { buffer = panel, silent = true })
end
local function context()
  local location = point(native_cursor())
  local record = by_id[location.id]
  local lines = { record.heading, "", "Source context (not selectable passage text)", "" }
  local function add(text)
    for _, line in ipairs(vim.split(tostring(text), "\n", { plain = true })) do lines[#lines + 1] = line end
  end
  add(record.context.path)
  add("Printed pages: " .. vim.json.encode(record.context.printed_pages))
  add("PDF pages: " .. vim.json.encode(record.context.pdf_pages))
  add("Attribution: " .. vim.json.encode(record.context.attribution))
  add("Record: " .. record.id)
  for _, warning in ipairs(record.warnings) do add("Warning: " .. warning) end
  for _, note in ipairs(record.notes) do
    add(""); add("Note attribution: " .. vim.json.encode(note.attribution))
    for _, warning in ipairs(note.warnings) do add("Warning: " .. warning) end
    add(note.plain_text)
  end
  add(""); add("Esc returns to reading. Notes and context have no passage-selection identity.")
  show_lines(lines)
end
local function help()
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
local function passage(delta)
  local row, selected = api.nvim_win_get_cursor(window)[1], nil
  if delta > 0 then
    for _, record in ipairs(records) do
      if positions[record.id].first_row > row then selected = record; break end
    end
  else
    for index = #records, 1, -1 do
      local record = records[index]
      if positions[record.id].first_row < row then selected = record; break end
    end
  end
  if selected then set_exact_cursor(source_point(selected.id, 0)); vim.cmd("normal! zt") end
end
for _, key in ipairs({ "q", "<C-q>" }) do
  vim.keymap.set({ "n", "x" }, key, guarded(function() export(); vim.cmd("qa!") end), { buffer = buffer, silent = true })
end
vim.keymap.set({ "n", "x" }, "j", "gj", { buffer = buffer, silent = true })
vim.keymap.set({ "n", "x" }, "k", "gk", { buffer = buffer, silent = true })
vim.keymap.set("n", "[p", guarded(function() passage(-1) end), { buffer = buffer, silent = true })
vim.keymap.set("n", "]p", guarded(function() passage(1) end), { buffer = buffer, silent = true })
vim.keymap.set("n", "c", guarded(context), { buffer = buffer, silent = true })
vim.keymap.set("n", "?", help, { buffer = buffer, silent = true })
api.nvim_create_user_command("SOLExport", guarded(export), {})
api.nvim_create_autocmd("VimResized", { callback = function()
  close_popup()
  if api.nvim_win_is_valid(window) then api.nvim_win_set_config(window, window_config()) end
end })

_G.SOLNvimReader = { records = records, buffer = buffer, window = window, positions = positions,
  source_rows = source_rows, namespace = namespace, styles = style_runs,
  source_location = source_location, source_point = source_point, capture = capture,
  restore = restore, export = export, validate_packet = validate_packet,
  byte_to_codepoint = byte_to_codepoint, codepoint_to_byte = codepoint_to_byte,
  verified_projection = verified_projection, context = context, help = help }
if data.restore ~= nil and data.restore ~= vim.NIL then restore(data.restore)
else set_exact_cursor(source_point(records[1].id, 0)) end
