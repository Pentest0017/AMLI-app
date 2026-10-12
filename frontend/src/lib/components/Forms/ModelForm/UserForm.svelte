<script lang="ts">
	import Select from '$lib/components/Forms/Select.svelte';
	import AutocompleteSelect from '../AutocompleteSelect.svelte';
	import TextField from '$lib/components/Forms/TextField.svelte';
	import TextArea from '$lib/components/Forms/TextArea.svelte';
	import type { SuperValidated } from 'sveltekit-superforms';
	import type { ModelInfo, CacheLock } from '$lib/utils/types';
	import { m } from '$paraglide/messages';
	import Checkbox from '$lib/components/Forms/Checkbox.svelte';
	import { page } from '$app/state';
	interface Props {
		form: SuperValidated<any>;
		model: ModelInfo;
		cacheLocks?: Record<string, CacheLock>;
		formDataCache?: Record<string, any>;
		shape?: any;
		context: string;
	}

	let {
		form,
		model,
		cacheLocks = {},
		formDataCache = $bindable({}),
		shape = {},
		context
	}: Props = $props();
</script>

<TextField
	{form}
	field="email"
	label={m.email()}
	cacheLock={cacheLocks['email']}
	bind:cachedValue={formDataCache['email']}
	data-focusindex="2"
/>
{#if shape.first_name !== undefined || shape.last_name !== undefined}
	<TextField
		{form}
		field="first_name"
		label={m.firstName()}
		cacheLock={cacheLocks['first_name']}
		bind:cachedValue={formDataCache['first_name']}
	/>
	<TextField
		{form}
		field="last_name"
		label={m.lastName()}
		cacheLock={cacheLocks['last_name']}
		bind:cachedValue={formDataCache['last_name']}
	/>
{/if}
{#if shape.designation !== undefined}
	<TextField
		{form}
		field="designation"
		label="Designation"
		cacheLock={cacheLocks['designation']}
		bind:cachedValue={formDataCache['designation']}
	/>
{/if}
{#if shape.department !== undefined}
	<TextField
		{form}
		field="department"
		label="Department"
		cacheLock={cacheLocks['department']}
		bind:cachedValue={formDataCache['department']}
	/>
{/if}
{#if shape.reports_to !== undefined}
	<AutocompleteSelect
		{form}
		optionsEndpoint="users?is_third_party=false&exclude_superadmin=true"
		optionsLabelField="user_name_designation"
		field="reports_to"
		cacheLock={cacheLocks['reports_to']}
		bind:cachedValue={formDataCache['reports_to']}
		label="Reports To"
	/>
{/if}
{#if shape.platform_role}
	<Select
		{form}
		field="platform_role"
		label="Platform Role"
		options={[
			{ value: 'user', label: 'User' },
			{ value: 'admin', label: 'Admin' },
			{ value: 'webadmin', label: 'Web Admin' },
			{ value: 'superadmin', label: 'Superadmin' }
		]}
		cacheLock={cacheLocks['platform_role']}
		bind:cachedValue={formDataCache['platform_role']}
	/>
{/if}

{#if context !== 'create'}
{#if shape.user_groups}
	<AutocompleteSelect
		{form}
		multiple
		optionsEndpoint="user-groups"
		field="user_groups"
		pathField="path"
		cacheLock={cacheLocks['user_groups']}
		bind:cachedValue={formDataCache['user_groups']}
		label={m.userGroups()}
	/>
{/if}
{#if shape.is_active}
	<Checkbox {form} field="is_active" label={m.isActive()} helpText={m.isActiveHelpText()} />
{/if}

{#if context !== 'create'}
	<Checkbox
		{form}
		field="keep_local_login"
		label={m.keepLocalLogin()}
		helpText={m.keepLocalLoginHelpText()}
	/>
{/if}
{#if shape.expiry_date && !page.data.object?.is_superuser}
	<TextField
		type="date"
		{form}
		field="expiry_date"
		label={m.expiryDate()}
		helpText={m.userExpiryHelpText()}
		cacheLock={cacheLocks['expiry_date']}
		bind:cachedValue={formDataCache['expiry_date']}
	/>
{/if}
<TextArea
	{form}
	field="observation"
	label={m.observation()}
	cacheLock={cacheLocks['observation']}
	bind:cachedValue={formDataCache['observation']}
/>
{/if}

{#if context === 'create'}
<span class="text-surface-600-400 pt-5">
	⚠️ An onboarding email will be automatically sent to the user.
</span>
{:else}
<span class="text-surface-600-400 pt-5">
	⚠️ {m.createdUserWillHaveNoRights()}
</span>
{/if}
