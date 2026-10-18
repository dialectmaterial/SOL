-- Exact Unicode/codepoint mapping and inert payload validation.
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

local function check_personal(personal)
  for _, items in pairs(personal.notes) do
    for _, item in ipairs(items) do
      if type(item.id) ~= "string" or type(item.lines) ~= "table" or type(item.edit_refusal) ~= "string"
        or (item.edit_refusal == "" and type(item.body) ~= "string")
        or (item.revision ~= vim.NIL and not integer(item.revision)) then fail("invalid personal note") end
    end
  end
end
local known_styles = { emphasis = true, strong = true, code = true, quotation = true, heading = true }
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

return {
  fail = fail,
  integer = integer,
  exact_keys = exact_keys,
  boundaries = boundaries,
  byte_to_codepoint = byte_to_codepoint,
  codepoint_to_byte = codepoint_to_byte,
  slice = slice,
  valid_styles = valid_styles,
  valid_strings = valid_strings,
  check_personal = check_personal,
}
