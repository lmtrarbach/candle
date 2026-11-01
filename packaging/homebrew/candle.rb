# Homebrew cask for Candle. After each release the workflow fills in the
# version and checksum below and pushes the result to
# github.com/lmtrarbach/homebrew-candle.
cask "candle" do
  version "{VERSION}"
  sha256 "{SHA256}"

  url "https://github.com/lmtrarbach/candle/releases/download/v#{version}/Candle-#{version}-macos-arm64.dmg"
  name "Candle"
  desc "Plan and write novels, chapter by chapter and scene by scene"
  homepage "https://candlewriter.com/"

  depends_on arch: :arm64

  app "Candle.app"

  # Project backups in ~/Library/Application Support/Candle are left alone.
  zap trash: [
    "~/Library/Preferences/com.candle.Candle.plist",
    "~/Library/Saved Application State/io.github.lmtrarbach.candle.savedState",
  ]

  caveats <<~EOS
    Candle isn't notarized by Apple. The first time you open it, macOS says it
    "can't be verified": open System Settings → Privacy & Security and click
    Open Anyway. You only need to do this once.
  EOS
end
