name: Run Channel Setup Script

on:
  workflow_dispatch:  # lets you trigger manually from GitHub Actions tab

permissions:
  contents: write

jobs:
  create-folders:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Run channel setup script
        run: |
          chmod +x setup_channels.sh
          ./setup_channels.sh

      - name: Commit and push new folders
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"
          git add .
          git commit -m "Auto-create all channel folders [skip ci]" || echo "No changes to commit"
          git push origin main
