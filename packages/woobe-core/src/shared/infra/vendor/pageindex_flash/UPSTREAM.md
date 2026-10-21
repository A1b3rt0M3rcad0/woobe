# Vendored PageIndex Flash subset

Source: VectifyAI/PageIndex, version 0.2.10, commit `27f284291724fbbbbe6976388bd53eed4ebe7fca`.
The upstream MIT license is preserved in `LICENSE`.

This subset contains the transitive Python import closure of upstream
`pageindex.flash.main.extract_toc` plus the five JSON data files that closure
reads. The Woobe Worker imports only this namespaced copy in its isolated
PageIndex child process. It does not import the PageIndex SDK root, local/cloud
clients, `utils`, chat, storage, or model optimization modules. The selected
`extract_toc(..., workers=1, use_embedded_toc=False)` path performs deterministic
PDF layout analysis and sends no model requests.

`vendor-manifest.json` records upstream-file hashes and sizes so later upgrades
can be reviewed against the pinned commit. This is an attributed source copy, not
a claim of compatibility with unselected PageIndex APIs.
