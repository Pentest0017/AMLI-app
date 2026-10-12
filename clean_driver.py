import re

# 1. SideBarNavigation.svelte
nav_file = 'frontend/src/lib/components/SideBar/SideBarNavigation.svelte'
with open(nav_file, 'r', encoding='utf-8') as f:
    nav = f.read()
nav = re.sub(r"import \{ driverInstance \} from '\$lib/utils/stores';\n?", '', nav)
nav = nav.replace('onclick={() => {\n\t\t\t\t\t\t\t\t$driverInstance?.moveNext();\n\t\t\t\t\t\t\t}}', '')
nav = nav.replace('onclick={() => {\n\t\t\t\t\t\t$driverInstance?.moveNext();\n\t\t\t\t\t}}', '')
with open(nav_file, 'w', encoding='utf-8') as f:
    f.write(nav)

# 2. [model=urlmodel]/+page.svelte
page_file = 'frontend/src/routes/(app)/(internal)/[model=urlmodel]/+page.svelte'
with open(page_file, 'r', encoding='utf-8') as f:
    page = f.read()
page = re.sub(r"import \{ driverInstance \} from '\$lib/utils/stores';\n?", '', page)
page = page.replace('onclick={() => {\n\t\t\t\t\t\t\t\t$driverInstance?.moveNext();\n\t\t\t\t\t\t\t}}', '')
with open(page_file, 'w', encoding='utf-8') as f:
    f.write(page)

# 3. stores.ts
stores_file = 'frontend/src/lib/utils/stores.ts'
with open(stores_file, 'r', encoding='utf-8') as f:
    stores = f.read()
stores = re.sub(r"export const driverInstance = writable<Driver \| null>\(null\);\n?", '', stores)
stores = re.sub(r"export const getStartedTrigger = writable\(false\);\n?", '', stores)
stores = re.sub(r"import type \{ Driver \} from 'driver\.js';\n?", '', stores)
with open(stores_file, 'w', encoding='utf-8') as f:
    f.write(stores)

# 4. +layout.svelte
layout_file = 'frontend/src/routes/(app)/+layout.svelte'
with open(layout_file, 'r', encoding='utf-8') as f:
    layout = f.read()
layout = layout.replace(',\n\t\tgetStartedTrigger', '')
layout = layout.replace(', getStartedTrigger', '')
with open(layout_file, 'w', encoding='utf-8') as f:
    f.write(layout)
