<script lang="ts">
	import { getI18nContext } from '$lib/i18n';
	import { toast } from 'svelte-sonner';
	import { onMount } from 'svelte';

	import {
		getWatchedDirectories,
		createWatchedDirectory,
		deleteWatchedDirectory,
		resyncWatchedDirectory,
		type WatchedDirectory
	} from '$lib/apis/filesystem';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import GarbageBin from '$lib/components/icons/GarbageBin.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';

	const i18n = getI18nContext();

	export let saveHandler: Function;

	let directories: WatchedDirectory[] | null = null;
	let newPath = '';
	let newName = '';
	let newExtensions = '.md,.txt,.pdf,.py,.ts,.js';
	let newExclude = '.git,node_modules,__pycache__,.venv';

	const loadDirectories = async () => {
		try {
			directories = await getWatchedDirectories(localStorage.token);
		} catch (err) {
			toast.error(`${err}`);
			directories = [];
		}
	};

	const addDirectory = async () => {
		if (!newPath || !newName) {
			toast.error($i18n.t('Path and name are required'));
			return;
		}

		try {
			await createWatchedDirectory(localStorage.token, {
				path: newPath,
				name: newName,
				extensions: newExtensions || undefined,
				exclude_patterns: newExclude || undefined
			});
			toast.success($i18n.t('Directory added'));
			newPath = '';
			newName = '';
			await loadDirectories();
		} catch (err) {
			toast.error(`${err}`);
		}
	};

	const removeDirectory = async (id: string) => {
		try {
			await deleteWatchedDirectory(localStorage.token, id);
			toast.success($i18n.t('Directory removed'));
			await loadDirectories();
		} catch (err) {
			toast.error(`${err}`);
		}
	};

	const resyncDirectory = async (id: string) => {
		toast.info($i18n.t('Resync started...'));
		try {
			await resyncWatchedDirectory(localStorage.token, id);
			toast.success($i18n.t('Resync complete'));
			await loadDirectories();
		} catch (err) {
			toast.error(`${err}`);
		}
	};

	onMount(async () => {
		await loadDirectories();
	});
</script>

<div class="flex flex-col h-full justify-between space-y-3 text-sm">
	{#if directories !== null}
		<div class="space-y-2.5 overflow-y-scroll scrollbar-hidden h-full pr-1.5">
			<div class="mb-3">
				<div class="mt-0.5 mb-2.5 text-base font-medium">
					{$i18n.t('Watched Directories')}
				</div>
				<div class="text-xs text-gray-500 dark:text-gray-400 mb-3">
					{$i18n.t(
						'Directories are monitored for changes and automatically synced to a Knowledge Base.'
					)}
				</div>
				<hr class="border-gray-100/30 dark:border-gray-850/30 my-2" />

				{#if directories.length > 0}
					<div class="space-y-2 mb-4">
						{#each directories as dir}
							<div
								class="flex items-center justify-between gap-2 p-3 rounded-xl bg-gray-50 dark:bg-gray-850"
							>
								<div class="flex-1 min-w-0">
									<div class="font-medium truncate">{dir.name}</div>
									<div class="text-xs text-gray-500 dark:text-gray-400 truncate">
										{dir.path}
									</div>
									{#if dir.extensions}
										<div class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
											{dir.extensions}
										</div>
									{/if}
									{#if dir.last_scan_at}
										<div class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
											{$i18n.t('Last scan')}: {new Date(
												dir.last_scan_at * 1000
											).toLocaleString()}
										</div>
									{/if}
								</div>
								<div class="flex items-center gap-1">
									<Tooltip content={$i18n.t('Resync')}>
										<button
											class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition"
											on:click={() => resyncDirectory(dir.id)}
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												fill="none"
												viewBox="0 0 24 24"
												stroke-width="1.5"
												stroke="currentColor"
												class="size-4"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182"
												/>
											</svg>
										</button>
									</Tooltip>
									<Tooltip content={$i18n.t('Remove')}>
										<button
											class="p-1.5 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/20 text-red-500 transition"
											on:click={() => removeDirectory(dir.id)}
										>
											<GarbageBin className="size-4" />
										</button>
									</Tooltip>
								</div>
							</div>
						{/each}
					</div>
				{:else}
					<div class="text-center text-gray-400 dark:text-gray-500 py-4 text-xs">
						{$i18n.t('No directories being watched.')}
					</div>
				{/if}

				<hr class="border-gray-100/30 dark:border-gray-850/30 my-3" />
				<div class="mt-0.5 mb-2 text-sm font-medium">{$i18n.t('Add Directory')}</div>

				<div class="space-y-2">
					<div>
						<label class="text-xs font-medium mb-0.5 block" for="fs-path"
							>{$i18n.t('Path')}</label
						>
						<input
							id="fs-path"
							class="w-full text-sm bg-transparent outline-hidden border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-1.5"
							bind:value={newPath}
							placeholder="/home/user/documents"
						/>
					</div>
					<div>
						<label class="text-xs font-medium mb-0.5 block" for="fs-name"
							>{$i18n.t('Name')}</label
						>
						<input
							id="fs-name"
							class="w-full text-sm bg-transparent outline-hidden border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-1.5"
							bind:value={newName}
							placeholder="My Documents"
						/>
					</div>
					<div>
						<label class="text-xs font-medium mb-0.5 block" for="fs-ext"
							>{$i18n.t('File Extensions (comma-separated)')}</label
						>
						<input
							id="fs-ext"
							class="w-full text-sm bg-transparent outline-hidden border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-1.5"
							bind:value={newExtensions}
							placeholder=".md,.txt,.pdf"
						/>
					</div>
					<div>
						<label class="text-xs font-medium mb-0.5 block" for="fs-exclude"
							>{$i18n.t('Exclude Patterns (comma-separated)')}</label
						>
						<input
							id="fs-exclude"
							class="w-full text-sm bg-transparent outline-hidden border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-1.5"
							bind:value={newExclude}
							placeholder=".git,node_modules"
						/>
					</div>
					<button
						class="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
						on:click={addDirectory}
					>
						<Plus className="size-3.5" />
						{$i18n.t('Add Directory')}
					</button>
				</div>
			</div>
		</div>
	{:else}
		<div class="flex justify-center py-8">
			<Spinner />
		</div>
	{/if}
</div>
