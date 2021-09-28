import hikari


async def error_embed(msg):
    e = hikari.Embed(color=hikari.Color.from_rgb(255, 0, 0))  # red
    e.set_author(name="🚫 Something went wrong!")
    e.description = msg
    return e


async def success_embed(msg):
    e = hikari.Embed(color=hikari.Color.from_rgb(0, 255, 0))  # green
    e.set_author(name="✔️ Success!")
    e.description = msg
    return e


async def info_embed(msg):
    e = hikari.Embed(color=hikari.Color.from_rgb(195, 195, 195))  # light grey
    e.set_author(name="Information:")
    e.description = msg
    return e


async def wip_embed():
    e = hikari.Embed(color=hikari.Color.from_rgb(185, 92, 0))  # dark orange
    e.set_author(name="🛠️ This command is under construction.")
    e.description = """This command isn't available yet.
Be sure to bug Evan about it because he loves that, and absolutely will not tell you to kill yourself."""
    return e
