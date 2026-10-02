# Third-party notices

This repository (`technical-cofounder`) is licensed under the Apache License,
Version 2.0 (see `LICENSE`). The components listed below are adapted from
MIT-licensed sources and remain under their original MIT terms; Apache-2.0
covers the rest of this repository.

Parts of this plugin's skills — option generation, skill authoring and
verification discipline — are adapted by Nova Caelum from obra/superpowers
(https://github.com/obra/superpowers), used under the MIT License:

    MIT License

    Copyright (c) 2025 Jesse Vincent

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the "Software"),
    to deal in the Software without restriction, including without limitation
    the rights to use, copy, modify, merge, publish, distribute, sublicense,
    and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
    THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.

Some engineering skills are adapted by Nova Caelum from its own public
no-mistakes repository (https://github.com/Nova-Caelum/no-mistakes), used
under the MIT License:

    MIT License

    Copyright (c) 2026 Nova Caelum & Co.

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the "Software"),
    to deal in the Software without restriction, including without limitation
    the rights to use, copy, modify, merge, publish, distribute, sublicense,
    and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
    THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.

The stress-test skill is adapted from mattpocock/skills
(https://github.com/mattpocock/skills), used under the MIT License:

    MIT License

    Copyright (c) 2026 Matt Pocock

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the "Software"),
    to deal in the Software without restriction, including without limitation
    the rights to use, copy, modify, merge, publish, distribute, sublicense,
    and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
    THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.

The overbloat-review skill adapts the tag taxonomy, structured output and
advise-only stance of DietrichGebert/ponytail
(https://github.com/DietrichGebert/ponytail), used under the MIT License:

    MIT License

    Copyright (c) 2026 DietrichGebert

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the "Software"),
    to deal in the Software without restriction, including without limitation
    the rights to use, copy, modify, merge, publish, distribute, sublicense,
    and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
    THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.

## Adapted components

Paths are relative to `plugins/`. Nova Caelum's own adaptations are
Apache-2.0; the upstream material they carry stays under its MIT terms above.

From obra/superpowers (MIT, Copyright (c) 2025 Jesse Vincent):
- `technical-cofounder/skills/option-conception/`: derived from `brainstorming`.
- `technical-cofounder/skills/pressure-scenario-skill-authoring/`: adapted from `writing-skills`, including its iron law and form-to-failure matching.

From Nova-Caelum/no-mistakes (MIT, Copyright (c) 2026 Nova Caelum & Co.):
- `technical-cofounder/skills/assumption-check/`: copied with light edits.
- `technical-cofounder/skills/verification-before-completion/` (with `references/`): copied with light edits; no-mistakes adapted it from obra/superpowers `verification-before-completion`.

From mattpocock/skills (MIT, Copyright (c) 2026 Matt Pocock):
- `technical-cofounder/skills/stress-test/`: adapted from `grill-me`.

From DietrichGebert/ponytail (MIT, Copyright (c) 2026 DietrichGebert):
- `technical-cofounder/skills/overbloat-review/`: tag taxonomy, structured output and advise-only stance adapted from `ponytail-review`.

Nova Caelum's own (Apache-2.0): the four agents, the registry,
`engineering-architecture`, `engineering-code-review`, `new-agent`, the setup
plugin (its `setup` skill, installer and scripts), the rules, the hooks, the local MCP server, and the super plugin's
`find-docs`, `web-research` and `get-api-keys`.
