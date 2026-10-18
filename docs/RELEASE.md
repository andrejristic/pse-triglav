# Making a release

Nothing is published without Andrej Ristic's "send".

1. Run the build by hand: GitHub -> Actions -> build -> Run workflow (or push a
   tag `vX.Y.Z` after Andrej's go-ahead). It tests, builds `pse-triglav_X.Y.Z_all.deb`
   and `triglav.exe`, and writes `SHA256SUMS`, as the artifact `release-files`.
2. Download `release-files` and check the sums: `sha256sum -c SHA256SUMS`.
3. **Andrej signs the sums** with his own key, on his own computer (Claude never
   handles the key or its passphrase):

       ssh-keygen -Y sign -f ~/.ssh/zerava_textbook -n zerava-release SHA256SUMS

   This writes `SHA256SUMS.sig`. Anyone can check it with the public key in
   `triglav/keys/allowed_signers` (namespace `zerava-release` is added there for
   releases).
4. Create the GitHub release on both repositories (zeravatechnologies and
   andrejristic) with the `.deb`, the `.exe`, `SHA256SUMS` and `SHA256SUMS.sig`.
5. Update the Downloads entry on zeravatech.ca (a PR).

Check a download:

    sha256sum -c SHA256SUMS
    ssh-keygen -Y verify -f allowed_signers -I andrej-ristic -n zerava-release -s SHA256SUMS.sig < SHA256SUMS
