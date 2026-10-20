-- Reader actions, source/personal-note context, outline, key bindings and lifecycle.
return function(reader)
  local api = vim.api
  local fail = reader.text.fail
  local byte_to_codepoint = reader.text.byte_to_codepoint
  local codepoint_to_byte = reader.text.codepoint_to_byte
  local check_personal = reader.text.check_personal
  local data = reader.view.data
  local integrated = reader.view.integrated
  local mode = reader.view.mode
  local focused_id = reader.view.focused_id
  local records = reader.view.records
  local by_id = reader.view.by_id
  local positions = reader.view.positions
  local source_rows = reader.view.source_rows
  local namespace = reader.view.namespace
  local style_runs = reader.view.style_runs
  local buffer = reader.view.buffer
  local window = reader.view.window
  local source_location = reader.view.source_location
  local source_point = reader.view.source_point
  local verified_projection = reader.view.verified_projection
  local native_cursor = reader.view.native_cursor
  local validate_packet = reader.view.validate_packet
  local capture = reader.view.capture
  local set_exact_cursor = reader.view.set_exact_cursor
  local normal_escape = reader.view.normal_escape
  local restore = reader.view.restore
  local export = reader.view.export
  local apply_theme = reader.view.apply_theme
  local search_namespace = reader.view.search_namespace
  local window_config = reader.view.window_config
  local cycle_theme = reader.view.cycle_theme
  local close_popup = reader.panels.close_popup
  local show_lines = reader.panels.show_lines
  local current_packet = reader.panels.current_packet
  local panels = reader.panels
  local request = reader.requests.request
  local reload = reader.requests.reload
  local toggle_mode = reader.requests.toggle_mode
  local toggle_focus = reader.requests.toggle_focus
  local source = reader.panels.source
  local source_pdf = reader.panels.source_pdf
  local note = reader.notes.note
  local open_footnote = reader.footnotes.open
  local show_footnote = reader.footnotes.show
  local attribution_line = reader.footnotes.attribution_line
  local function context(...) return reader.context(...) end
  local function search()
    -- Standard command-line input works in any Neovim-capable terminal. A cancelled
    -- query never visits a result or modifies canonical text/selection.
    local query = vim.fn.input('Search book: ')
    if query:match('%S') then request('search', {query = query}) end
  end
  local function page()
    -- A printed page, as the edition numbers it and the status line shows it.
    local answer = vim.fn.input('Printed page: ')
    local number = tonumber(answer:match('^%s*[Pp]?%.?%s*(%d+)%s*$') or '')
    if number then request('page_open', {page = number})
    elseif answer:match('%S') then vim.notify('Type a printed page number, e.g. 240', vim.log.levels.WARN) end
  end
  local function landmark()
    local name = vim.fn.input('Name this place: ')
    if name:match('%S') then request('landmark_set', {name = name}) end
  end
  local function marker(slot, operation)
    request(operation or 'marker_set', {slot = slot})
  end
  -- The system clipboard: the program Python chose from the real session,
  -- else the terminal itself through OSC 52. Returns how it was copied.
  local function copy(text)
    local clipboard = vim.json.decode(vim.env.SOL_NVIM_CLIPBOARD or 'null', {luanil = {object = true, array = true}})
    if type(clipboard) == 'table' and type(clipboard.command) == 'table' then
      -- No output pipes: wl-copy leaves a process behind that would hold them open.
      local ok, result = pcall(function()
        return vim.system(clipboard.command, {stdin = text, env = clipboard.env, stdout = false, stderr = false}):wait(3000)
      end)
      if ok and type(result) == 'table' and result.code == 0 then return 'clipboard' end
    end
    local ok = pcall(function() require('vim.ui.clipboard.osc52').copy('+')(vim.split(text, '\n', {plain = true}), 'v') end)
    return ok and 'terminal' or nil
  end
  local order = {}
  for index, record in ipairs(records) do order[record.id] = index end
  -- A selection end on a blank line or heading moves to the nearest prose
  -- inside the selection: forward for its start, back for its end.
  local function endpoint(row, byte, last)
    if source_rows[row] then
      local location = source_location(row, byte)
      if last then location.offset = math.min(by_id[location.id]._length, location.offset + 1) end
      return location
    end
    local nearest
    for candidate in pairs(source_rows) do
      if (last and candidate < row or not last and candidate > row)
          and (not nearest or math.abs(candidate - row) < math.abs(nearest - row)) then nearest = candidate end
    end
    if not nearest then fail('select some passage text to copy') end
    local item = source_rows[nearest]
    return {id = item.id, offset = last and item.finish or item.start}
  end
  -- Exact source text: the selection, across paragraphs if need be (joined by
  -- a blank line), or the current paragraph without one.
  local function selected_text()
    local visual = vim.fn.mode(1)
    if visual ~= 'v' and visual ~= 'V' then
      return by_id[current_packet().reference.reference.target_id].plain_text
    end
    local a, b = vim.fn.getpos('v'), vim.fn.getpos('.')
    if b[2] < a[2] or (b[2] == a[2] and b[3] < a[3]) then a, b = b, a end
    local first = endpoint(a[2], visual == 'V' and 0 or a[3] - 1, false)
    local last_byte = visual == 'V' and math.max(0, #(api.nvim_buf_get_lines(buffer, b[2] - 1, b[2], false)[1] or '') - 1)
      or b[3] - 1
    local last = endpoint(b[2], last_byte, true)
    local from, to = order[first.id], order[last.id]
    if from > to or (from == to and first.offset >= last.offset) then fail('select some passage text to copy') end
    local slice = reader.text.slice
    if from == to then return slice(records[from].plain_text, first.offset, last.offset) end
    local parts = {slice(records[from].plain_text, first.offset, records[from]._length)}
    for index = from + 1, to - 1 do parts[#parts + 1] = records[index].plain_text end
    parts[#parts + 1] = slice(records[to].plain_text, 0, last.offset)
    return table.concat(parts, '\n\n')
  end
  local function yank()
    verified_projection()
    local text = selected_text()
    vim.fn.setreg('"', text, 'v')
    if vim.fn.mode(1) ~= 'n' then normal_escape() end
    local how = copy(text)
    local count = vim.fn.strchars(text)
    if not how then
      fail('Could not reach the system clipboard; the text is in Neovim\'s register only')
    end
    api.nvim_echo({{('Copied %d characters%s'):format(count,
      how == 'terminal' and ' (through the terminal)' or ''), 'None'}}, false, {})
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
    local implementation = reader.load('neovim_tree')
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
  -- A UTC stamp "2026-10-17T12:00:00Z" in local time, as "17 Oct 2026, 14:00";
  -- anything else unchanged.
  local MONTHS = {'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'}
  local function when(stamp)
    local y, m, d, hh, mm = tostring(stamp):match('^(%d%d%d%d)%-(%d%d)%-(%d%d)T(%d%d):(%d%d)')
    if not y or not MONTHS[tonumber(m)] then return tostring(stamp) end
    -- os.time reads a table as local time; correct it by the zone's offset then.
    local guess = os.time({year = tonumber(y), month = tonumber(m), day = tonumber(d),
      hour = tonumber(hh), min = tonumber(mm), sec = 0, isdst = false})
    local offset = os.time(os.date('*t', guess)) - os.time(os.date('!*t', guess))
    local shown = os.date('*t', guess + offset)
    return ('%d %s %d, %02d:%02d'):format(shown.day, MONTHS[shown.month], shown.year, shown.hour, shown.min)
  end
  local function words(value) return (tostring(value):gsub('_', ' ')) end
  reader.context = function(origin)
    local packet = origin or current_packet()
    local record = by_id[packet.reference.reference.target_id]
    local lines, marks = {}, {}
    local note_rows, book_rows = {}, {}
    local function add(text, group)
      for _, line in ipairs(vim.split(tostring(text), "\n", { plain = true })) do
        lines[#lines + 1] = line
        if group then marks[#marks + 1] = {#lines, group} end
      end
    end
    -- A section: its name stands out, its keys stay quiet beside it.
    local function section(name, hint)
      add('')
      add(name .. (hint and hint ~= '' and ('   ' .. hint) or ''))
      marks[#marks + 1] = {#lines, 'SOLSourceHeading', 0, #name}
      if hint and hint ~= '' then marks[#marks + 1] = {#lines, 'NonText', #name} end
    end
    add(record.heading, 'SOLSourceHeading')
    local where = reader.view.breadcrumb(record.context.path)
    if where ~= '' then add(where, 'NonText') end
    local printed, pdf = record.context.printed_pages, record.context.pdf_pages
    local function span(range)
      if range[1] == nil or range[1] == vim.NIL then return nil end
      if range[2] == nil or range[2] == vim.NIL or range[2] == range[1] then return tostring(range[1]) end
      return range[1] .. '–' .. range[2]
    end
    local page_parts = {}
    if span(printed) then page_parts[#page_parts + 1] = 'p. ' .. span(printed) end
    if span(pdf) then page_parts[#page_parts + 1] = 'PDF p. ' .. span(pdf) end
    if #page_parts > 0 then add(table.concat(page_parts, ' · '), 'NonText') end
    if #record.warnings > 0 then add('') end
    for _, warning in ipairs(record.warnings) do add('! ' .. warning, 'SOLSourceWarning') end

    section('Footnotes', #record.notes == 0 and 'none' or (#record.notes .. ' · Enter reads one'))
    for _, note in ipairs(record.notes) do
      local first = #lines + 1
      add('  [' .. (note.label ~= '' and note.label or '?') .. '] ' .. attribution_line(note.attribution))
      for _, warning in ipairs(note.warnings) do add('      ! ' .. warning, 'SOLSourceWarning') end
      book_rows[#book_rows + 1] = {first = first, last = #lines, id = note.reference.reference.target_id}
    end
    if data.personal then
      if not data.personal.persistent then
        section('Your notes', 'need a workspace; this session saves nothing')
      else
        local mine = data.personal.notes[record.id] or {}
        section('Your notes', (#mine == 0 and 'none' or tostring(#mine)) .. ' · a add' ..
          (#mine > 0 and ' · e edit · r versions' or ''))
        for index, item in ipairs(mine) do
          if index > 1 then add('') end
          local first = #lines + 1
          add('  ' .. item.author .. ' · ' .. when(item.created_at) ..
            (item.revision ~= vim.NIL and (' · revision ' .. tostring(item.revision)) or ''), 'NonText')
          if item.changed_source then add('  the passage has changed since this note was written', 'SOLSourceWarning') end
          if item.retired_target then add('  written on a retired record ID; shown here through its successor', 'NonText') end
          if item.edit_refusal ~= "" then add('  ' .. item.edit_refusal, 'NonText') end
          for _, line in ipairs(item.lines) do add('  ' .. line) end
          note_rows[#note_rows + 1] = { first = first, last = #lines, item = item }
        end
      end
    end
    if data.markers then
      section('Markers', "m1–3 set · '1–3 go · dm1–3 clear" .. (data.markers.persistent and '' or ' · this session only'))
      for _, slot in ipairs(data.markers.slots) do
        add('  ' .. tostring(slot.slot) .. '  ' .. slot.label .. (slot.resolved == record.id and '   ← here' or ''))
      end
    end
    section('About this text')
    local attribution = record.context.attribution
    if type(attribution) == 'table' and attribution.author then
      local how = {}
      for _, key in ipairs({'role', 'status'}) do
        if type(attribution[key]) == 'string' and attribution[key] ~= '' then how[#how + 1] = words(attribution[key]) end
      end
      add('  Author   ' .. attribution.author .. (#how > 0 and (' (' .. table.concat(how, ', ') .. ')') or ''))
    end
    add('  Section  ' .. #records .. ' paragraphs loaded; gg/G stay in them')
    add('  Record   ' .. record.id, 'NonText')
    add('')
    add('Esc returns to reading', 'NonText')
    show_lines(lines, packet, marks)
    panels.context_open = true
    local panel = api.nvim_get_current_buf()
    vim.keymap.set('n', '<CR>', function()
      local row, chosen = api.nvim_win_get_cursor(panels.window)[1], nil
      for _, span in ipairs(book_rows) do
        if row >= span.first and row <= span.last then chosen = span.id end
      end
      if not chosen then
        vim.notify('Move onto a book footnote first.', vim.log.levels.INFO); return
      end
      open_footnote({chosen}, packet)
    end, {buffer = panel, silent = true})
    -- The note under the cursor, or the only one; never a guess between several.
    local function chosen()
      local row = api.nvim_win_get_cursor(0)[1]
      for _, span in ipairs(note_rows) do
        if row >= span.first and row <= span.last then return span.item end
      end
      if #note_rows == 1 then return note_rows[1].item end
      fail(#note_rows == 0 and 'there are no workspace notes on this passage'
        or 'move the cursor onto one of the notes first')
    end
    vim.keymap.set('n', 'e', function()
      local ok, problem = pcall(function() note(chosen()) end)
      if not ok then vim.notify(tostring(problem), vim.log.levels.ERROR) end
    end, { buffer = panel, silent = true })
    vim.keymap.set('n', 'r', function()
      local ok, problem = pcall(function() request('note_history', { note = chosen().id }) end)
      if not ok then vim.notify(tostring(problem), vim.log.levels.ERROR) end
    end, { buffer = panel, silent = true })
    if data.markers then
      for slot = 1, 3 do
        local number = slot
        vim.keymap.set('n', tostring(number), function() request('marker_open', {slot = number}) end,
          {buffer = api.nvim_get_current_buf(), silent = true})
      end
    end
  end
  local function help()
    if integrated then
      -- Sections of key / description; a wrapped description continues under
      -- its own column, and the section names carry the heading colour.
      local KEY = 17
      local sections = {
        { "Reading", {
          { "j/k  Ctrl-d/u", "lines / half a window" },
          { "h/l  w", "character / word motions" },
          { "b / n", "previous / next paragraph" },
          { "gg / G", "start / end of the loaded section" },
          { "p", "continuous or one-paragraph reading" },
          { "f", "quiet focus mode" },
          { "T", "theme: Mocha, Latte, Paper, Night, Terminal (this session)" } } },
        { "Finding your way", {
          { "t", "book outline: h/l fold, Enter read" },
          { "gp", "go to a printed page, e.g. gp 240 Enter" },
          { "/", "search the whole book" },
          { "Ctrl-P / Ctrl-N", "previous / next search occurrence" },
          { "Esc", "hide the search marks" },
          { "Alt-Left/Right", "back / forward through your reading" },
          { "m1 m2 m3", "set a paragraph marker; '1 '2 '3 jump, dm1… clear" },
          { "M / L", "name this place / list named places (Enter reads)" } } },
        { "Text, sources and notes", {
          { "v  then y", "select; copy to the clipboard, across paragraphs too" },
          { "mouse", "scroll; drag to select and copy" },
          { "c", "beside the text: pages, footnotes, your notes, markers" },
          { "c, Enter", "read a footnote; Backspace back, Esc to the passage" },
          { "s", "the printed page of this passage (formulas)" },
          { "S", "the whole printed page in a PDF viewer, to zoom" },
          { "a", "write a note on this passage (workspace)" },
          { "c, e / r", "edit your note / its earlier versions" } } },
        { "ESSENCE", {
          { "E", "open beside the reader; inside, Alt-F fullscreen, Alt-R back" } } },
        { "Leaving", {
          { ":q  :qa", "save your exact place and quit" },
          { ":qa!", "quit without saving" } } },
      }
      local lines, marks = { "SOL reader · " .. (mode == "paragraph" and "one paragraph" or "continuous") }, { { 1, "SOLSourceHeading" } }
      for _, section in ipairs(sections) do
        lines[#lines + 1] = ""
        lines[#lines + 1] = section[1]
        marks[#marks + 1] = { #lines, "SOLSourceHeading" }
        for _, row in ipairs(section[2]) do
          lines[#lines + 1] = row[1] .. string.rep(" ", math.max(1, KEY - vim.fn.strdisplaywidth(row[1]))) .. row[2]
        end
      end
      for _, note in ipairs({ "", "In one-paragraph reading j/k stay in the paragraph; b/n move on.",
          "Selections are not saved; the book's text cannot be edited.", "Esc closes this help." }) do
        lines[#lines + 1] = note
        if note ~= "" then marks[#marks + 1] = { #lines, "NonText" } end
      end
      show_lines(lines, nil, marks, KEY)
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
  if integrated then
    -- Quitting is a command, not a stray key: q and Ctrl-q only say how.
    for _, key in ipairs({ "q", "<C-q>" }) do
      vim.keymap.set({ "n", "x" }, key, function()
        api.nvim_echo({{"Type :q to save your place and quit (:qa! quits without saving)", "None"}}, false, {})
      end, { buffer = buffer, silent = true })
    end
    -- :q, :qa and their spellings save the exact position first; :qa! (any
    -- command with !) is left to Neovim and quits without saving.
    local quits = {}
    for _, name in ipairs({ "q", "qu", "qui", "quit", "qa", "qal", "qall", "quita", "quital", "quitall",
                            "wq", "wqa", "wqal", "wqall", "x", "xa", "xal", "xall", "xi", "xit", "exi", "exit" }) do
      quits[name] = true
    end
    vim.keymap.set("c", "<CR>", function()
      -- From a selection, ":" starts with its range; the selection is kept.
      local line = vim.fn.getcmdline()
      local selected = line:match("^%s*'<,'>") ~= nil
      if vim.fn.getcmdtype() == ":" and quits[vim.trim(line:gsub("^%s*'<,'>", ""), nil)] then
        vim.schedule(guarded(function()
          if selected then vim.cmd("normal! gv") end
          reading_request("quit")
        end))
        return "<C-c>"
      end
      return "<CR>"
    end, { buffer = buffer, expr = true })
  else
    for _, key in ipairs({ "q", "<C-q>" }) do
      vim.keymap.set({ "n", "x" }, key, guarded(function() reading_request("quit") end), { buffer = buffer, silent = true })
    end
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
    for _, release in ipairs({'<LeftRelease>', '<2-LeftRelease>', '<3-LeftRelease>'}) do
      vim.keymap.set('x', release, guarded(yank), {buffer = buffer, silent = true})
    end
    vim.keymap.set('n', 't', guarded(tree), {buffer = buffer, silent = true})
    vim.keymap.set('n', 'f', guarded(toggle_focus), {buffer = buffer, silent = true})
    vim.keymap.set('n', 'b', guarded(function() passage(-1) end), {buffer = buffer, silent = true})
    vim.keymap.set('n', 'n', guarded(function() passage(1) end), {buffer = buffer, silent = true})
    vim.keymap.set('n', '/', guarded(search), {buffer = buffer, silent = true})
    vim.keymap.set('n', 'gp', guarded(page), {buffer = buffer, silent = true})
    vim.keymap.set('n', 'M', guarded(landmark), {buffer = buffer, silent = true})
    vim.keymap.set('n', 'L', guarded(function() request('landmark_list') end), {buffer = buffer, silent = true})
    vim.keymap.set({'n', 'x'}, 'E', guarded(function()
      -- Capture the exact position and selection; ESSENCE returns to it with
      -- Alt-R and on closing. Visual mode stays until ESSENCE actually opens
      -- (its window change ends it), so a refused launch keeps the selection.
      local packet = current_packet()
      local essence = rawget(_G, 'SOLEssence')
      essence.origin = packet
      if essence.window and api.nvim_win_is_valid(essence.window) then essence.focus()
      else request('essence_open', nil, nil, packet) end
    end), {buffer = buffer, silent = true})
    -- Views rebuilt from this one (p, f, b/n) copy data, so forget the marks there too.
    vim.keymap.set('n', '<Esc>', function()
      api.nvim_buf_clear_namespace(buffer, search_namespace, 0, -1)
      data.search_marks = vim.NIL
    end, {buffer = buffer, silent = true})
    vim.keymap.set('n', 's', guarded(source), {buffer = buffer, silent = true})
    vim.keymap.set('n', 'S', guarded(source_pdf), {buffer = buffer, silent = true})
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
  vim.keymap.set({"n", "x"}, "c", guarded(context), { buffer = buffer, silent = true })
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
    relayout = function()
      if api.nvim_win_is_valid(window) then api.nvim_win_set_config(window, window_config()) end
    end,
    marker_slots = function() return vim.deepcopy(data.markers) end,
    update_markers = function(markers)
      data.markers = markers
      if panels.context_open then context() end
    end,
    update_personal = function(personal)
      check_personal(personal)
      data.personal = personal
      if panels.context_open then context() end
    end,
    footnote = show_footnote,
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

end
