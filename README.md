# SentryBot
A discord/fluxer bot (discord.py) that looks for those dreaded 4-image-scams and pings online/idle mods to deal with them.

Requires only base permissions to see and send messages. Additional permissions can be assigned to the `SentryBot` role (kick member, ban member, manage messages, or manage members), with which the bot will kick, ban, delete, or timeout (depending on permissions granted).

You will need to put your email address in the `useragent` file, your discord bot token in `discord_token` file, and install requirements. Have fun!

Because this needs to track what mods are online, and scan messages, it needs all the privileged intents: 
<img width="2106" height="489" alt="image" src="https://github.com/user-attachments/assets/139039fe-0a64-44e3-80cc-6729b9e70e0a" />


If you want to add the public version:

🔗Invite: https://discord.com/oauth2/authorize?client_id=1517141264443773059

📧Email: sentrybot@excessive.space (please send any scam images the bot doesn't recognize)

💬Message: .damaged


Config files:

You need to have 3 config files to use all the features.

1. `useragent` - this takes an email to shove in your UA so sites can contact you.
2. `discord_token` - this is your token for your bot. see Discord to get one.
3. `.cloudflade_config.json` - a file to configure the S3 compatible storage. See below:

```json
{
  "ACCESS_KEY_ID": "",
  "SECRET_ACCESS_KEY": "",
  "S3_API_ENDPOINT": "",
  "BUCKET_NAME": ""
}
```
