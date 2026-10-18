-- Native SOL reader entry. Load implementation only beside this package file.
-- Python owns corpus verification; modules own disposable native reader state.
local supplied = ...
local source = debug.getinfo(1, 'S').source
assert(source:sub(1, 1) == '@', 'SOL reader needs its installed Lua entry file')
local directory = vim.fn.fnamemodify(source:sub(2), ':p:h')
local function load_module(name)
  assert(name:match('^neovim_[a-z_]+$'), 'invalid SOL reader module')
  return assert(loadfile(directory .. '/' .. name .. '.lua'))()
end
for _, server in ipairs(vim.fn.serverlist()) do pcall(vim.fn.serverstop, server) end
local reader = {load = load_module}
reader.reload = function(payload)
  return assert(loadfile(directory .. '/neovim.lua'))(payload)
end
reader.text = load_module('neovim_text')
if supplied == nil and vim.env.SOL_NVIM_SPLASH == '1' then
  -- Start-up placeholder: the first page arrives over the action channel.
  return load_module('neovim_splash')(reader)
end
reader.view = load_module('neovim_view')(reader, supplied)
reader.panels = load_module('neovim_panels')(reader)
reader.requests = load_module('neovim_requests')(reader)
reader.footnotes = load_module('neovim_footnotes')(reader)
reader.notes = load_module('neovim_notes')(reader)
load_module('neovim_controls')(reader)
