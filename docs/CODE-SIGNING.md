# Code signing the Windows .exe for free (SignPath Foundation)

*Checked against https://signpath.org/terms on 18 October 2026. Read the terms
again before applying; they can change.*

## Kratko, na našem

- Windows bez potpisa pokazuje upozorenje "nepoznat izdavač". Komercijalni
  certifikat košta oko $200-400 godišnje.
- **SignPath Foundation potpisuje besplatno open source projekte.** Triglav
  (GPL-3.0, javni repo, gradi se u GitHub Actions) ispunjava uslove.
- **Kao izdavač na potpisu piše "SignPath Foundation", a ne Zerava.** To je
  cijena besplatnog potpisa.
- Prijavljuje se Andrej ili Dhiraj (otvara nalog na ime projekta). Svi u timu
  moraju imati dvostepenu prijavu (MFA) i na SignPathu i na GitHubu.
- Prvo izdanje (v1.0) izlazi nepotpisano, jer SignPath traži da je program već
  izdan u obliku koji se potpisuje. Potpisana su izdanja nakon odobrenja.

## What it is

Without a signature, Windows SmartScreen warns that the publisher is unknown.
A commercial code-signing certificate costs roughly USD 200-400 a year and its
key must live on a hardware token or a cloud signing service. SignPath
Foundation signs open source software **free of charge**: it checks that each
binary was built from the project's public source by its CI, and signs it
with its own certificate.

**The publisher shown on the signature is "SignPath Foundation", not Zerava
Technologies Inc.** That is the price of free signing.

## Conditions (summarised from the terms)

- An OSI-approved licence for all components, with **no commercial
  dual-licensing**. Triglav is GPL-3.0 only.
- No malware, no potentially unwanted programs, no proprietary code (system
  libraries may be included).
- Actively maintained, and **already released in the form to be signed** --
  so v1.0 goes out unsigned first.
- Functionality described on the download page.
- The team signs only its own code, built from its own repository.
- No tools that actively scan for or exploit vulnerabilities (Triglav is
  defensive: it watches agents on its own system and never touches another).
- Respects privacy and security, announces system changes, can be uninstalled.
- **Verifiable builds**: binaries built automatically from the repository by
  CI (our `.github/workflows/build.yml`), and **each release approved by hand**.
- **Multi-factor authentication** for every team member, on SignPath and on
  GitHub.
- **Defined roles**: authors, reviewers, approvers (who approve each signing).
- A **code signing policy** on the home and download pages (text below), with a
  privacy policy.
- Product name and version set in SignPath.
- Help with any investigation if a violation is reported.

## Steps

1. Release v1.0 unsigned (docs/RELEASE.md).
2. Turn on MFA for everyone on GitHub (zeravatechnologies, andrejristic, Dhiraj).
3. Put the code signing policy (below) on zeravatech.ca next to the download.
4. Apply at https://signpath.org/apply for `zeravatechnologies/pse-triglav`.
   Roles: authors and approvers -- Andrej Ristic; reviewer -- Dhiraj Sah (or as
   you decide).
5. When approved, add the secret `SIGNPATH_API_TOKEN` (and the organisation and
   project IDs SignPath gives) to the repository's Actions secrets.
6. Tell Claude: the placeholder step in `build.yml` (`SIGNPATH_ON`) is then
   replaced by SignPath's GitHub action, and every later `.exe` is signed after
   an approver approves it in SignPath.

## Code signing policy (text for the download page)

> Free code signing for the Windows build of PSE Triglav is provided by
> SignPath.io, certificate by SignPath Foundation. Binaries are built by GitHub
> Actions from the public repository github.com/zeravatechnologies/pse-triglav;
> every signing is approved by hand. Team: Andrej Ristic (author, approver),
> Dhiraj Sah (reviewer). Privacy: PSE Triglav sends nothing off your computer
> unless you choose an online model for the voice; see the README.
