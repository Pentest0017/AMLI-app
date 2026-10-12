<script lang="ts">
	import EmailTemplatesSettings from '$lib/components/Settings/EmailTemplatesSettings.svelte';
</script>

<div class="p-6 space-y-6">
	<div class="flex items-center justify-between border-b border-surface-200-800 pb-4">
		<div>
			<h1 class="h2 font-bold flex items-center gap-3">
				<i class="fa-solid fa-envelope-open-text text-primary-500"></i>
				Mail Templates Management
			</h1>
			<p class="text-sm text-surface-600-400 mt-1">
				System email templates editor & branding customization for administrators.
			</p>
		</div>
	</div>

	<EmailTemplatesSettings />
</div>
