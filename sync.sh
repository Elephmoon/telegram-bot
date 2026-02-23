#!/bin/bash

VAULT="$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/MyVault"
REMOTE="user@YOUR_VM_IP:/home/botuser/telegram-bot/tasks/"
SSH_KEY="$HOME/.ssh/vm_bot"

rsync -avz --update \
  -e "ssh -i $SSH_KEY -o ConnectTimeout=5" \
  "$REMOTE" \
  "$VAULT/Tasks/"
