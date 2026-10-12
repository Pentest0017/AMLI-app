import re

with open('frontend/src/lib/components/SideBar/SideBar.svelte', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('driverInstance, tableHandlers, getStartedTrigger', 'tableHandlers')

content = re.sub(r"import \{ driver \} from 'driver\.js';\n?", '', content)
content = re.sub(r"import 'driver\.js/dist/driver\.css';\n?", '', content)
content = re.sub(r"import '\./driver-custom\.css';\n?", '', content)
content = re.sub(r"import FirstLoginModal from '\$lib/components/Modals/FirstLoginModal\.svelte';\n?", '', content)

content = re.sub(r'const steps = \[.*?\];', '', content, flags=re.DOTALL)
content = re.sub(r'function triggerVisit\(\) \{.*?return true;\n\t\}', '', content, flags=re.DOTALL)
content = re.sub(r'// Watch for trigger from the top bar.*?\$effect\(\(\) => \{.*?\}\);', '', content, flags=re.DOTALL)
# also remove the comments that were left behind:
content = re.sub(r'// id is not needed.*?svelte-js-files\n', '', content, flags=re.DOTALL)

with open('frontend/src/lib/components/SideBar/SideBar.svelte', 'w', encoding='utf-8') as f:
    f.write(content)
