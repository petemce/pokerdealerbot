# pokerdealerbot
Slack bot that deals NLHE / PLO poker

Original game idea taken from https://github.com/tiko23867/python3-poker

It's very rough around the edges, doesn't do side pots or all in properly yet, coming very soon.

Needs a legacy slack bot token as the new granular permission system doesn't seem to allow access to the realtime api, which this needs. export SLACK_BOT_TOKEN="xoxb...."

Also requires python 3.5 or newer for async stuff. Add it to any channel you're in (not a busy channel as it is verbose and will annoy people who don't like poker) and it will listen for the following commands:

start game 2 

Starts heads up nlhe when said by 2 people

start plo 2 

Starts heads up plo when said by 2 people

bet NNN 

with NNN being amount, use bet 0 to check. Starting stacks are 20k, bb is 200

fold 

Folds and starts another game
