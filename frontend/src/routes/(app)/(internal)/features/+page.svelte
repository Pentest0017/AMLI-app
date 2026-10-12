<script lang="ts">
    import { pageTitle } from '$lib/utils/stores';
    import { navData } from '$lib/components/SideBar/navData';
    import { safeTranslate } from '$lib/utils/i18n';
    import LoadingSpinner from '$lib/components/utils/LoadingSpinner.svelte';
    import { enhance } from '$app/forms';
    import { invalidateAll } from '$app/navigation';
    import type { PageData, ActionData } from './$types';

    let { data, form }: { data: PageData; form: ActionData } = $props();

    $effect(() => {
        $pageTitle = 'Access Rights Matrix';
    });

    function buildToggleState(serverToggles: any[]) {
        const stateMap: Record<string, any> = {};
        if (serverToggles) {
            serverToggles.forEach((t: any) => {
                stateMap[t.key] = { ...t };
            });
        }
        navData.items.forEach((category) => {
            category.items.forEach((item) => {
                if (!stateMap[item.name]) {
                    stateMap[item.name] = {
                        key: item.name,
                        name: item.name,
                        parent_key: category.name,
                        enabled_for_web_admin: true,
                        enabled_for_admin: true,
                        enabled_for_user: true
                    };
                }
            });
        });
        return stateMap;
    }

    let toggles = $state<Record<string, any>>(buildToggleState(data.toggles));

    $effect(() => {
        if (data.toggles) {
            toggles = buildToggleState(data.toggles);
        }
    });

    let serializedToggles = $derived(JSON.stringify(Object.values(toggles)));
    let saving = $state(false);
</script>

<div class="card p-4 h-full flex flex-col gap-4 overflow-auto">
    <div class="flex justify-between items-center">
        <h2 class="h2">Access Rights Matrix</h2>
        <form method="POST" action="?/save" use:enhance={({ formData }) => {
            formData.set('toggles', JSON.stringify(Object.values(toggles)));
            saving = true;
            return async ({ update }) => {
                saving = false;
                await update();
                await invalidateAll();
            };
        }}>
            <input type="hidden" name="toggles" value={serializedToggles} />
            <button type="submit" class="btn variant-filled-primary cursor-pointer" disabled={saving}>
                {#if saving} <LoadingSpinner /> {:else} Save Changes {/if}
            </button>
        </form>
    </div>

    {#if data.error}
        <div class="alert variant-filled-error">{data.error}</div>
    {/if}
    {#if form?.error}
        <div class="alert variant-filled-error">{form.error}</div>
    {/if}
    {#if form?.success}
        <div class="alert variant-filled-success">Access Rights saved successfully!</div>
    {/if}

    <div class="table-container">
        <table class="table table-hover">
            <thead>
                <tr>
                    <th>Category</th>
                    <th>Feature / Menu</th>
                    <th class="text-center">Web Admin Access</th>
                    <th class="text-center">Admin Access</th>
                    <th class="text-center">User Access</th>
                </tr>
            </thead>
            <tbody>
                {#each navData.items as category}
                    {#each category.items as item, i}
                        <tr>
                            {#if i === 0}
                                <td rowspan={category.items.length} class="font-bold align-top">
                                    {safeTranslate(category.name)}
                                </td>
                            {/if}
                            <td>
                                <div class="flex items-center gap-2">
                                    <i class="{item.fa_icon}"></i>
                                    {safeTranslate(item.name)}
                                </div>
                            </td>
                            <td class="text-center">
                                <input 
                                    type="checkbox" 
                                    class="checkbox cursor-pointer" 
                                    checked={toggles[item.name]?.enabled_for_web_admin ?? true} 
                                    onchange={(e) => {
                                        if (toggles[item.name]) {
                                            toggles[item.name] = {
                                                ...toggles[item.name],
                                                enabled_for_web_admin: (e.target as HTMLInputElement).checked
                                            };
                                        }
                                    }}
                                />
                            </td>
                            <td class="text-center">
                                <input 
                                    type="checkbox" 
                                    class="checkbox cursor-pointer" 
                                    checked={toggles[item.name]?.enabled_for_admin ?? true} 
                                    onchange={(e) => {
                                        if (toggles[item.name]) {
                                            toggles[item.name] = {
                                                ...toggles[item.name],
                                                enabled_for_admin: (e.target as HTMLInputElement).checked
                                            };
                                        }
                                    }}
                                />
                            </td>
                            <td class="text-center">
                                <input 
                                    type="checkbox" 
                                    class="checkbox cursor-pointer" 
                                    checked={toggles[item.name]?.enabled_for_user ?? false} 
                                    onchange={(e) => {
                                        if (toggles[item.name]) {
                                            toggles[item.name] = {
                                                ...toggles[item.name],
                                                enabled_for_user: (e.target as HTMLInputElement).checked
                                            };
                                        }
                                    }}
                                />
                            </td>
                        </tr>
                    {/each}
                {/each}
            </tbody>
        </table>
    </div>
</div>
