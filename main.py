# --- 1. RED ALERT SYSTEM HACK (.alert) ---
# Ye screen ko Red (🔴) aur White (⬜) flash karega Alarm ki tarah
@bot.on_message(filters.command("alert", prefixes=".") & filters.me)
async def red_alert_prank(client, message):
    try:
        # 10 baar flash karega
        for i in range(5):
            await message.edit("🔴 **WARNING: SYSTEM BREACH DETECTED!** 🔴\n🚨 **HACKER IS HERE** 🚨")
            await asyncio.sleep(0.5)
            await message.edit("⬜ **WARNING: SYSTEM BREACH DETECTED!** ⬜\n💀 **HACKER IS HERE** 💀")
            await asyncio.sleep(0.5)
        
        await message.edit("❌ **SYSTEM DESTROYED** ❌\n(Phone Reboot Required)")
    except Exception as e:
        print(e)

# --- 2. NUCLEAR BLAST (.nuke) ---
# Ek chhota bomb girega aur fir BADA DHAMAKA hoga
@bot.on_message(filters.command("nuke", prefixes=".") & filters.me)
async def nuke_blast(client, message):
    try:
        # Bomb Gir raha hai
        await message.edit("☁️\n\n\n       💣\n\n\n🏠🏠🏠")
        await asyncio.sleep(0.5)
        await message.edit("☁️\n\n\n\n       💣\n\n🏠🏠🏠")
        await asyncio.sleep(0.5)
        await message.edit("☁️\n\n\n\n\n       💣\n🏠🏠🏠")
        await asyncio.sleep(0.5)
        
        # IMPACT
        await message.edit("💥 **BOOM!** 💥")
        await asyncio.sleep(0.2)
        
        # Bada Dhamaka (Art)
        explosion_art = """
        🔥🔥🔥🔥🔥🔥
      🔥  💀  💀  🔥
    🔥   DESTRUCTION  🔥
      🔥  💀  💀  🔥
        🔥🔥🔥🔥🔥🔥
        """
        await message.edit(f"**{explosion_art}**")
        await asyncio.sleep(2)
        await message.edit("🌪️ **Sab Raakh Ho Gaya...** 🌪️")
    except:
        pass

# --- 3. AIRPLANE AIRSTRIKE (.air) ---
# Plane chalega -> Bomb Girega -> Plane Udh Jayega
@bot.on_message(filters.command("air", prefixes=".") & filters.me)
async def airstrike(client, message):
    try:
        # Plane Left se Right jayega
        sky_frames = [
            "✈️ . . . . . . . . . . 🏢",
            ". . ✈️ . . . . . . . . 🏢",
            ". . . . ✈️ . . . . . . 🏢",
            ". . . . . . ✈️ . . . . 🏢", # Yahan Bomb Girega
            ". . . . . . ✈️ 💣 . . . 🏢",
            ". . . . . . . . ✈️ . 💣 🏢",
            ". . . . . . . . . . ✈️ 💥", # Impact
            ". . . . . . . . . . . . ✈️"  # Plane Exit
        ]

        for frame in sky_frames:
            await message.edit(f"☁️ **AIR STRIKE INCOMING** ☁️\n\n{frame}")
            await asyncio.sleep(0.8)
        
        await message.edit("🎯 **Target Eliminated!**\nMission Passed. +Respect")
    except:
        pass

# --- 4. ROTATING TEXT (.roll <text>) ---
# Text ghumega (Scroll karega) news ki tarah
# Use: .roll MERA BOT SABKA BAAP
@bot.on_message(filters.command("roll", prefixes=".") & filters.me)
async def rolling_text(client, message):
    try:
        # Command se text nikalo
        if len(message.command) < 2:
            original_text = " HACKER IN THE GROUP "
        else:
            original_text = " " + message.text.split(maxsplit=1)[1] + " "

        # Scrolling Logic
        text = original_text * 2 # Text ko duplicate kiya smooth scroll ke liye
        
        # 15 steps tak ghumega
        for i in range(len(original_text)):
            display_text = text[i : i+15] # 15 words ka window
            await message.edit(f"💻 **SYSTEM STATUS:**\n`| {display_text} |`")
            await asyncio.sleep(0.3)
            
        await message.edit(f"✅ **{original_text.strip()}**")
    except:
        pass
