<script lang="ts">
	import { resolvedTheme } from '$lib/utils/theme';

	interface Props {
		height?: number;
		width?: number;
	}

	let { height, width }: Props = $props();
	let isDark = $derived($resolvedTheme === 'dark');
</script>

{#if isDark}
	<img
		class="h-20 sm:h-24 w-full object-contain max-w-[240px] drop-shadow-lg py-1 transition-all"
		src="/logo-dark.png?v=20260903"
		alt="Max Life Insurance"
		data-testid="logo-image"
	/>
{:else}
	<img
		class="h-20 sm:h-24 w-full object-contain max-w-[240px] drop-shadow-md py-1 transition-all"
		src="/logo-light.png?v=20260903"
		alt="Max Life Insurance"
		data-testid="logo-image"
	/>
{/if}
