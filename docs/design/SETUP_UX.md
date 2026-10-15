# Agent and provider setup

First-Agent setup follows one sequence: Project → Agent instructions → Model → Review → First test. The progress list uses the actual current step. Headings and actions explain the next outcome; the Agent is created only after review and the first message is sent separately in the Playground.

Forms use natural content height and a scrolling page, with actions immediately after the fields. The model list has its own bounded scroll area. At narrow widths the progress list wraps above the form. Inter serves fields, actions and explanations; Georgia serves editorial headings; JetBrains Mono serves ordinal numbers and model/key identifiers. Existing operational Light/Dark colors and shared components remain authoritative. The owner's rejected setup capture is the problem reference; `04-dark-agent-grid.png` supplies the quiet dark surface separation, without introducing an illustration layout or scaling real controls.

Required Agent fields have associated labels, linked inline errors and focus on the first invalid field. The optional description explains that it does not change behavior. The support example is an explicit action and preserves a name already entered. Review provides direct instructions/model editing. Leaving through Exit setup confirms unsaved form loss; browser reload/close also warns. Saved resources remain available. These guards do not claim to intercept every browser-history navigation.

## What is saved

| Action | Persistent result | Next action |
| --- | --- | --- |
| Create Project and continue | Project | Name the Agent and describe its objective. |
| Save connection | Provider connection with a typed Project key reference and destination metadata | Configure Draft access; no discovery, inference or deployment occurs on save. |
| Declare key | Secret declaration, automatically selected as the reference | Set its value separately if authorized. |
| Set Draft API key | Value in the central Draft configuration store | Review destination access; a saved value does not establish provider validity. |
| Approve use | Explicit environment/consumer/destination approval | Continue to model selection. |
| Save model and review | Project generation Model bound to its provider connection | Review and create the Agent. Returning from review reuses this Model. |
| Create Agent Draft | Agent with its objective and selected model/connection | Opens the first-run Playground; no test message is sent automatically. |
| Send a Playground message | Runtime request using the selected environment | Inspect the result; provider charges may apply. |

Browsing a provider catalog can invoke external model discovery through the backend. It is separate from inference. Saved Project models can be selected without creating a new connection or Model. Catalog failure offers retry, Draft access configuration and manual model ID entry. A failed Model save preserves selection; a failed Agent save preserves review and reuses the already saved Model.

## Provider connections

New connection forms show one choice per supported provider family; the legacy `custom` alias is retained for existing definitions rather than offered as a duplicate new option. All providers accept a recognizable connection name. Compatible endpoints receive local URL feedback, while the backend remains the authority for destination policy.

The same central Draft value and usage editors are reachable after saving a provider from first-Agent setup, normal Agent creation, Model creation and Credentials. They preserve the surrounding form. Values remain separate from the connection creation payload and do not enter React Query mutation caches. Existing environment permissions and explicit destination approvals remain enforced; there is no automatic grant, inference or deployment. Legacy credential storage and explicit legacy routes stay on their migration path in Environments; the new shortcut never writes direct environment values for a legacy reference. Operators can still use Environments for all environments. Permission failures show unavailable configuration rather than a false ready state.

Connection details distinguish enabled status from external validation, explain empty model groups and wrap controls inside the dialog. Revoke/archive actions appear in a separate labelled disclosure and retain the existing usage inspection and confirmation. The Overview keeps only its header environment controls; configuration context is read-only and follows that selection. The All view explicitly reports Draft configuration because the summary API accepts one environment.

## Validation

Commands, source commit, counts and capture metadata are recorded in [validation.json](validation.json). The production browser suite includes complete creation, back/edit/retry behavior, no duplicate Model writes, declaration auto-selection, Draft value/approval entry, compatible endpoint validation, permission denial, existing models, catalog failure and the single Overview filter. Layout checks cover 2560, 1440, 768 and 390px in both themes; selected axe rules supplement manual review.

The committed gallery contains only main pages, including first-Agent setup, at desktop/tablet/mobile widths. Provider modal and detailed setup review captures remain in ignored test output. Synthetic API fixtures qualify the real browser UI without exercising a live provider or backend deployment. Local checks do not establish completion of remote CI or complete accessibility certification.
