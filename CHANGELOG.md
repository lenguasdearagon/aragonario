# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## main

## [0.7] - 2025-03-17

- [added] Permalinks: access specific word definition using a permanent link.
- [added] Monolingual definition.
- [fixed] `importdata` fails if verbosity >= 2

## [0.6] - 2023-01-01

- [added] Lexicons with topic.
- [added] Entries can be labelled (e.g. groups, categories...)

## [0.5] - 2021-09-01

- [added] Command `marktranslations` which finds & marks related words of
  reverse lexicon on entries. This information is stored on new field
  `marked_translation` of `Entry` model and it's exposed on the API.

## [0.4.1] - 2021-04-12

- [fixed] API: include lexicon code on `word` payload.

## [0.4] - 2021-04-07

- [added] Support multiple lexicons.
- [added] API: Added Lexicon api view and Lexicon serializer
- [changed] Added database constraints:
  - Avoid duplicated word in a lexicon (unique together lexicon and term)
  - Avoid repeated entries (unique together word, translation and variation)
- [changed] Import management commands requires lexicon_code paramenter
- [changed] API: View WordViewSet requires a parameter l (lexicon_code) to perform search and near methods.

## [0.3.2] - 2020-01-27

- [fixed] `importvariation` handle properly variation param on dry-run.
- [fixed] Issue #83 searchs that starts with signs of punctuation.

## [0.3.1] - 2020-01-16

- [changed] `importvariation` supports XLSX with multiple sheets.
- [changed] `importvariation` provide default gramcat when column B is missing (or
  error if getting default fails).
- [fixed] `importvariation` error when translation (column C) is missing.

## [0.3] - 2020-01-03

- [added] Diatopic variation validator view.
- [changed] `--variation` is optional on `importvariation` management command.
- [fixed]: `importvariation` ignore extra columns on XLSX file.

## [0.2] - 2019-07-29

- [added] Add support to diatopic variations
- [fixed] duplicated word gramcats

## [0.1] - 2019-04-12

- [added] API: retrieve and search words by term.
- [added] API: retrieve gramatical categories.
- [added] Add view to validate XLSX data.
