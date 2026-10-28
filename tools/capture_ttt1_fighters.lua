-- MAME 0.289, tektagt World TEG2/VER.C1. Saves the moveset of whoever P1 has highlighted on the character select:
-- K = Kazuya, H = Heihachi, J = Jin. Each press writes <name>-select-ram.bin (main RAM, as capture_jun_import.lua)
-- and <name>.png (the screen, so the export can show who it was). No ROM data embedded.
local machine=manager.machine
local space=machine.devices[":maincpu"].spaces["program"]
local input=machine.input
local screen=machine.screens[":screen"]
local port=machine.ioport.ports[":JVS_PLAYER1"]
local coin=machine.ioport.ports[":JVS_COIN1"]
local keys={{"KEYCODE_K","kazuya","Kazuya"},{"KEYCODE_H","heihachi","Heihachi"},{"KEYCODE_J","jin","Jin"}}
for _,k in ipairs(keys) do k.code=input:code_from_token(k[1]);k.down=false end
local frame=0
local said="Highlight a fighter: K saves Kazuya, H Heihachi, J Jin. Esc when done."
local function dump(name)
    local f=assert(io.open(name.."-select-ram.bin","wb"))
    f:write(space:read_range(0,0x3fffff,8));f:close()
    screen:snapshot(name..".png")
end
dojo_capture=emu.add_machine_frame_notifier(function()
    frame=frame+1
    -- Coin and start as the Jun capture does; press 5 and 1 yourself if the select screen doesn't come up.
    if frame==1800 then coin.fields["Coin 1"]:set_value(1) end
    if frame==1804 then coin.fields["Coin 1"]:set_value(0) end
    if frame==1860 then port.fields["1 Player Start"]:set_value(1) end
    if frame==1864 then port.fields["1 Player Start"]:set_value(0) end
    for _,k in ipairs(keys) do
        local down=input:code_pressed(k.code)
        if down and not k.down then dump(k[2]);said="Saved "..k[3]..". K Kazuya, H Heihachi, J Jin; Esc when done." end
        k.down=down
    end
    screen:draw_text(4,4,said,0xffffffff,0xc0000000)
end)
