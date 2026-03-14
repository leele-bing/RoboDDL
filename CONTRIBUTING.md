# Contributing to RoboDDL

Most contributions to RoboDDL fall into four categories:

- Data additions and updates
- Bug fixes
- Feature requests
- Others

Most actual PRs are still data updates.

## Contribution types

### Data additions and updates

- Add or update venue metadata in [`src/data/conference`](./src/data/conference) or [`src/data/journal`](./src/data/journal).
- Verify every changed field against an official source.
- If you only need to fix a deadline, source link, rank, or venue metadata, you will usually edit a single YAML file.

### Bug fixes

- Use this for broken UI, wrong countdown behavior, parsing issues, layout regressions, or incorrect filtering behavior.
- Include clear reproduction steps, expected behavior, and screenshots if the bug is visual.

### Feature requests

- Use this for new pages, filters, sorting behavior, data fields, workflow improvements, or larger UX changes.
- Explain the use case and why the feature would help RoboDDL users.

### Others

- Use this for documentation cleanup, refactors, discussion topics, housekeeping, and anything that does not fit the three categories above.

## Quick workflow

1. Identify which contribution type your change belongs to.
2. Update the relevant files.
3. Verify sources or behavior.
4. Run:

```bash
npm install
npm run build
```

5. If you changed the UI, also check desktop and a narrow mobile viewport.
6. Open a PR or issue with enough context for review.

Useful commands:

```bash
npm run dev
npm run preview
```

## What to edit

- Conference data: [`src/data/conference`](./src/data/conference)
- Journal data: [`src/data/journal`](./src/data/journal)
- Venue loader: [`src/data/loadVenueRecords.ts`](./src/data/loadVenueRecords.ts)
- Conference normalization: [`src/data/conferences.ts`](./src/data/conferences.ts)
- Timezone helpers: [`src/utils/dateUtils.ts`](./src/utils/dateUtils.ts)
- Main UI: [`src/App.tsx`](./src/App.tsx)

## Data rules

### Conferences

- Use `submissionModel: "deadline"`.
- Keep `knownEditions` up to date.
- Include `paperDeadline`, `timezone`, `conferenceDates`, `location`, and source links for official editions.
- If the next edition is not announced yet, keep the latest official edition and let the site estimate the next cycle.
- `abstractDeadline` is optional.
- Use `cycleYears: 2` only for non-annual venues such as `ECCV`.
- `futureHints` is optional and only meant for future date/location/link context when the next deadline is still estimated.

### Journals

- Use `submissionModel: "rolling"`.
- Fill `ccfRank`, `caaiRank`, `casPartition`, and `jcrQuartile` when known.
- Use `"N/A"` when a metric is unavailable or the venue is not listed.
- `sourceUrl` should support the rolling-submission claim with an official journal or publisher page.
- `specialIssueLabel` and `specialIssueUrl` are optional, but should be added together when relevant.

## YAML rules

Venue files are parsed by a small custom loader in [`src/data/loadVenueRecords.ts`](./src/data/loadVenueRecords.ts), so keep them intentionally simple:

- Quote all string values with double quotes. Example: `title: "ICRA"`.
- Keep real numbers unquoted. Example: `year: 2027`.
- Use spaces, not tabs.
- Do not add YAML comments beginning with `#`.
- Do not use advanced YAML features such as anchors, inline objects, or complex multiline syntax.
- Keep `venueType: "conference"` files in `src/data/conference` and `venueType: "journal"` files in `src/data/journal`.

Behavior details worth knowing:

- For conferences, the newest official item in `knownEditions` is the fallback reference for future estimation.
- The app assumes conferences are annual unless `cycleYears` says otherwise.
- If `abstractDeadline` exists and is still in the future, the countdown targets it before `paperDeadline`.
- Supported timezones come from [`src/utils/dateUtils.ts`](./src/utils/dateUtils.ts): `AoE`, `PST`, `PDT`, `EST`, `EDT`, `UTC`, `GMT`, and `UTC±HH[:MM]`.

## Templates

Delete optional lines that do not apply instead of leaving placeholder content behind.

<details>
<summary>Conference template</summary>

```yaml
slug: "venue-slug"
title: "VENUE"
fullTitle: "Full Conference Title"
summary: "One-sentence summary of the venue scope and why it belongs in RoboDDL."
venueType: "conference"
category: "RAS"
ccfRank: "B"
caaiRank: "A"
homepage: "https://series-homepage.example.com/"
dblp: "conf/example"
keywords:
  - "keyword 1"
  - "keyword 2"
submissionModel: "deadline"
cycleYears: 1
knownEditions:
  - year: 2027
    paperDeadline: "2026-09-15T23:59:59"
    abstractDeadline: "2026-09-08T23:59:59"
    timezone: "AoE"
    conferenceDates: "May 20-24, 2027"
    location: "City, Country"
    link: "https://2027.venue.example.com/"
    deadlineSourceLabel: "VENUE 2027 Call for Papers"
    deadlineSourceUrl: "https://2027.venue.example.com/call-for-papers/"
    note: "Optional extra context shown on the card."
futureHints:
  - year: 2028
    conferenceDates: "May 18-22, 2028"
    location: "Another City, Country"
    link: "https://future-meetings.example.com/"
    note: "Optional future-meeting note."
```

Conference notes:

- Required top-level fields: `slug`, `title`, `fullTitle`, `summary`, `venueType`, `category`, `homepage`, `submissionModel`, `knownEditions`.
- `cycleYears`, `ccfRank`, `caaiRank`, `dblp`, `keywords`, `abstractDeadline`, `note`, and `futureHints` are optional.
- `knownEditions` should contain official editions, not guesses.
- Prefer official CFP or official event pages for `deadlineSourceUrl`.
- Use the real local deadline with the correct `timezone`; the app converts it for display.
- Conference categories should stay aligned with existing filters unless you are also updating the UI logic.
</details>

<details>
<summary>Journal template</summary>

```yaml
slug: "journal-slug"
title: "Journal Short Name"
fullTitle: "Full Journal Title"
summary: "One-sentence summary of the journal's robotics relevance and positioning."
venueType: "journal"
category: "Journal"
caaiRank: "A"
ccfRank: "B"
casPartition: "CAS 2"
jcrQuartile: "Q1"
homepage: "https://journal-homepage.example.com/"
dblp: "journals/example"
keywords:
  - "journal keyword 1"
  - "journal keyword 2"
submissionModel: "rolling"
rollingNote: "Rolling submission. Manuscripts are handled continuously."
sourceLabel: "Official journal page"
sourceUrl: "https://journal-homepage.example.com/"
specialIssueLabel: "Special Issue"
specialIssueUrl: "https://journal-homepage.example.com/special-issue"
```

Journal notes:

- Required top-level fields: `slug`, `title`, `fullTitle`, `summary`, `venueType`, `category`, `homepage`, `submissionModel`, `rollingNote`, `sourceLabel`, `sourceUrl`.
- `dblp`, `keywords`, `specialIssueLabel`, and `specialIssueUrl` are optional.
- Prefer keeping `caaiRank`, `ccfRank`, `casPartition`, and `jcrQuartile` present, using `"N/A"` when needed.
</details>

## Issues and PRs

Open an issue for:

- Data additions and updates that need confirmation before implementation
- Bug reports
- Feature requests
- Others such as docs, cleanup, or discussion topics

Include:

- A short description of the change or problem
- Relevant venue name or affected page
- Source URL if the issue is about data
- Reproduction steps if the issue is a bug
- Screenshot if the issue is visual

In a PR description, include:

- Which contribution type it belongs to
- What changed
- Why it changed
- Source links used, if applicable

Suggested PR checklist:

- [ ] I identified the contribution type
- [ ] I updated the relevant files
- [ ] I added or updated source links when needed
- [ ] I ran `npm run build`
- [ ] I checked the affected UI if I changed layout or styling
