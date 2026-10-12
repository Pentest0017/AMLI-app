<script lang="ts">
	import { breadcrumbs, goto, type Breadcrumb } from '$lib/utils/breadcrumbs';

	interface Props {
		href?: string;
		breadcrumbAction?: 'push' | 'replace';
		label?: string;
		prefixCrumbs?: Breadcrumb[];
		stopPropagation?: boolean;
		children?: import('svelte').Snippet;
		[key: string]: any;
	}

	let {
		href = '',
		breadcrumbAction = 'push',
		label = '',
		prefixCrumbs = [],
		stopPropagation = false,
		children,
		...rest
	}: Props = $props();

	const handleClick = (event: MouseEvent) => {
		const navLabel: string = label || (event.target as HTMLElement)?.innerText || (event.currentTarget as HTMLElement)?.innerText || 'Nav';

		const crumb = { label: navLabel, href };
		const _crumbs = [...prefixCrumbs, crumb];
		breadcrumbs[breadcrumbAction](_crumbs);

		if (href && (stopPropagation || href.startsWith('/'))) {
			event.stopPropagation();
			event.preventDefault();
			goto(href, { label: navLabel, breadcrumbAction });
		}
	};
</script>

<a aria-label={label || undefined} onclick={handleClick} {href} {...rest}>
	{@render children?.()}
</a>
