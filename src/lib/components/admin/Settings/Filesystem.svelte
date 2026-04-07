<script lang="ts">
	import { getI18nContext } from '$lib/i18n';
	import { toast } from 'svelte-sonner';
	import { onMount } from 'svelte';

	import {
		getWatchedDirectories,
		createWatchedDirectory,
		deleteWatchedDirectory,
		resyncWatchedDirectory,
		browseDirectories,
		getFilesystemStats,
		clearDirectoryIndex,
		type WatchedDirectory,
		type FilesystemStats
	} from '$lib/apis/filesystem';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import { getRAGConfig, updateRAGConfig } from '$lib/apis/retrieval';
	import GarbageBin from '$lib/components/icons/GarbageBin.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';

	const i18n = getI18nContext();

	export let saveHandler: Function;

	let directories: WatchedDirectory[] | null = null;
	let newPath = '';
	let newName = '';
	let newExtensions = '.md,.txt,.pdf,.py,.ts,.js';
	let newExclude = '.git,node_modules,__pycache__,.venv';
	let autoContextEnabled = true;
	let autoContextLoading = true;
	let stats: FilesystemStats | null = null;
	let showFileTypes = false;

	// Folder picker state
	let showBrowser = false;
	let browserPath = '';
	let browserDirs: string[] = [];
	let browserLoading = false;

	const openBrowser = async () => {
		showBrowser = true;
		browserLoading = true;
		try {
			const res = await browseDirectories(localStorage.token, newPath || undefined);
			browserPath = res.path;
			browserDirs = res.dirs;
		} catch (err) {
			toast.error(`${err}`);
		}
		browserLoading = false;
	};

	const navigateTo = async (dir: string) => {
		browserLoading = true;
		try {
			const target = browserPath === '/' ? `/${dir}` : `${browserPath}/${dir}`;
			const res = await browseDirectories(localStorage.token, target);
			browserPath = res.path;
			browserDirs = res.dirs;
		} catch (err) {
			toast.error(`${err}`);
		}
		browserLoading = false;
	};

	const navigateUp = async () => {
		const parent = browserPath.substring(0, browserPath.lastIndexOf('/')) || '/';
		browserLoading = true;
		try {
			const res = await browseDirectories(localStorage.token, parent);
			browserPath = res.path;
			browserDirs = res.dirs;
		} catch (err) {
			toast.error(`${err}`);
		}
		browserLoading = false;
	};

	const selectBrowserPath = () => {
		newPath = browserPath;
		if (!newName) {
			newName = browserPath.split('/').filter(Boolean).pop() || '';
		}
		showBrowser = false;
	};

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

	const toggleAutoContext = async () => {
		try {
			await updateRAGConfig(localStorage.token, {
				ENABLE_FILESYSTEM_AUTO_CONTEXT: autoContextEnabled
			});
			toast.success($i18n.t('Settings saved'));
		} catch (err) {
			toast.error(`${err}`);
			autoContextEnabled = !autoContextEnabled;
		}
	};

	const refreshStats = async () => {
		try {
			stats = await getFilesystemStats(localStorage.token);
		} catch (err) {
			console.error('Failed to refresh stats:', err);
		}
	};

	const clearIndex = async (id: string, name: string) => {
		if (!confirm($i18n.t('Clear all indexed data for "{{name}}"? This will require a re-scan.', { name }))) {
			return;
		}
		try {
			await clearDirectoryIndex(localStorage.token, id);
			toast.success($i18n.t('Index cleared'));
			await loadDirectories();
			await refreshStats();
		} catch (err) {
			toast.error(`${err}`);
		}
	};

	const getScanStatusColor = (ageSeconds: number | null): string => {
		if (ageSeconds === null) return 'bg-red-500';
		if (ageSeconds < 86400) return 'bg-green-500';
		if (ageSeconds < 604800) return 'bg-yellow-500';
		return 'bg-red-500';
	};

	const getDirStats = (dirId: string) => {
		return stats?.directories?.find((d) => d.id === dirId) || null;
	};

	onMount(async () => {
		await loadDirectories();
		try {
			const config = await getRAGConfig(localStorage.token);
			autoContextEnabled = config.ENABLE_FILESYSTEM_AUTO_CONTEXT ?? true;
		} catch (err) {
			console.error('Failed to load auto-context config:', err);
		}
		autoContextLoading = false;
		try {
			stats = await getFilesystemStats(localStorage.token);
		} catch (err) {
			console.error('Failed to load stats:', err);
		}
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
				<div class="flex w-full justify-between items-center mt-2 mb-1">
					<div>
						<div class="self-center text-xs font-medium">
							{$i18n.t('Auto-inject local files as context')}
						</div>
						<div class="text-xs text-gray-400 dark:text-gray-500">
							{$i18n.t('Automatically use watched files as context in all conversations')}
						</div>
					</div>
					<div class="flex items-center">
						{#if autoContextLoading}
							<Spinner className="size-4" />
						{:else}
							<Switch
								bind:state={autoContextEnabled}
								on:change={toggleAutoContext}
							/>
						{/if}
					</div>
				</div>
				{#if stats}
					<div class="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3">
						<div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-850">
							<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Files Indexed')}</div>
							<div class="text-lg font-bold mt-0.5">
								{stats.completed_files.toLocaleString()}
								<span class="text-xs font-normal text-gray-400">/ {stats.total_files.toLocaleString()}</span>
							</div>
						</div>
						<div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-850">
							<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Chunks')}</div>
							<div class="text-lg font-bold mt-0.5">{stats.total_chunks.toLocaleString()}</div>
						</div>
						<div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-850">
							<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Disk Usage')}</div>
							<div class="text-lg font-bold mt-0.5">{(stats.vector_db_size_bytes / 1024 / 1024).toFixed(1)} MB</div>
						</div>
						<div class="p-3 rounded-lg {stats.failed_files > 0 ? 'bg-red-50 dark:bg-red-900/20' : 'bg-gray-50 dark:bg-gray-850'}">
							<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Failed')}</div>
							<div class="text-lg font-bold mt-0.5 {stats.failed_files > 0 ? 'text-red-600 dark:text-red-400' : ''}">{stats.failed_files}</div>
						</div>
					</div>

					{#if Object.keys(stats.file_types).length > 0}
						<button
							class="text-xs text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 mt-2 transition"
							on:click={() => (showFileTypes = !showFileTypes)}
						>
							{showFileTypes ? $i18n.t('Hide file types') : $i18n.t('Show file types')}
						</button>
						{#if showFileTypes}
							<div class="flex flex-wrap gap-2 mt-1">
								{#each Object.entries(stats.file_types) as [ext, count]}
									<span class="text-xs px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
										{ext}: {count.toLocaleString()}
									</span>
								{/each}
							</div>
						{/if}
					{/if}
				{/if}
				<hr class="border-gray-100/30 dark:border-gray-850/30 my-2" />

				{#if directories.length > 0}
					<div class="space-y-2 mb-4">
						{#each directories as dir}
							<div
								class="flex items-center justify-between gap-2 p-3 rounded-xl bg-gray-50 dark:bg-gray-850"
							>
								<div class="flex-1 min-w-0">
									<div class="flex items-center gap-2">
										{#if getDirStats(dir.id)}
											<span class="w-2 h-2 rounded-full flex-shrink-0 {getScanStatusColor(getDirStats(dir.id)?.last_scan_age_seconds ?? null)}" title="{getDirStats(dir.id)?.last_scan_age_seconds !== null ? Math.floor((getDirStats(dir.id)?.last_scan_age_seconds ?? 0) / 3600) + 'h ago' : 'Never scanned'}"></span>
										{/if}
										<span class="font-medium truncate">{dir.name}</span>
									</div>
									<div class="text-xs text-gray-500 dark:text-gray-400 truncate">
										{dir.path}
									</div>
									{#if getDirStats(dir.id)?.file_count}
										<div class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
											{getDirStats(dir.id)?.file_count.toLocaleString()} {$i18n.t('files indexed')}
										</div>
									{/if}
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
									<Tooltip content={$i18n.t('Clear Index')}>
										<button
											class="p-1.5 rounded-lg hover:bg-amber-100 dark:hover:bg-amber-900/20 text-amber-600 transition"
											on:click={() => clearIndex(dir.id, dir.name)}
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
													d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
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
						<div class="flex gap-2">
							<input
								id="fs-path"
								class="flex-1 text-sm bg-transparent outline-hidden border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-1.5"
								bind:value={newPath}
								placeholder="/home/user/documents"
							/>
							<button
								class="px-3 py-1.5 text-sm font-medium border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition"
								on:click={openBrowser}
							>
								{$i18n.t('Browse')}
							</button>
						</div>
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

{#if showBrowser}
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
		on:mousedown|self={() => (showBrowser = false)}
		on:keydown={(e) => e.key === 'Escape' && (showBrowser = false)}
	>
		<div
			class="bg-white dark:bg-gray-900 rounded-2xl shadow-xl w-full max-w-lg mx-4 flex flex-col max-h-[70vh]"
		>
			<div class="flex items-center justify-between px-4 pt-4 pb-2">
				<div class="text-sm font-medium">{$i18n.t('Select Directory')}</div>
				<button
					class="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition"
					on:click={() => (showBrowser = false)}
				>
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="size-4">
						<path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
					</svg>
				</button>
			</div>

			<div class="px-4 pb-2">
				<div class="text-xs text-gray-500 dark:text-gray-400 font-mono truncate bg-gray-50 dark:bg-gray-850 rounded-lg px-3 py-1.5">
					{browserPath}
				</div>
			</div>

			<div class="flex-1 overflow-y-auto px-4 min-h-0">
				{#if browserLoading}
					<div class="flex justify-center py-6"><Spinner /></div>
				{:else}
					<div class="space-y-0.5">
						{#if browserPath !== '/'}
							<button
								class="flex items-center gap-2 w-full text-left px-3 py-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition text-sm"
								on:click={navigateUp}
							>
								<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="size-4 text-gray-400">
									<path fill-rule="evenodd" d="M14 8a.75.75 0 0 1-.75.75H4.56l3.22 3.22a.75.75 0 1 1-1.06 1.06l-4.5-4.5a.75.75 0 0 1 0-1.06l4.5-4.5a.75.75 0 0 1 1.06 1.06L4.56 7.25h8.69A.75.75 0 0 1 14 8Z" clip-rule="evenodd" />
								</svg>
								<span class="text-gray-500 dark:text-gray-400">..</span>
							</button>
						{/if}
						{#each browserDirs as dir}
							<button
								class="flex items-center gap-2 w-full text-left px-3 py-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition text-sm"
								on:click={() => navigateTo(dir)}
							>
								<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="size-4 text-yellow-500">
									<path d="M2 3.5A1.5 1.5 0 0 1 3.5 2h2.879a1.5 1.5 0 0 1 1.06.44l1.122 1.12A1.5 1.5 0 0 0 9.62 4H12.5A1.5 1.5 0 0 1 14 5.5v1.401a2.986 2.986 0 0 0-1.5-.401h-9c-.546 0-1.059.146-1.5.401V3.5Z" />
									<path d="M2 9.5v3A1.5 1.5 0 0 0 3.5 14h9a1.5 1.5 0 0 0 1.5-1.5v-3A1.5 1.5 0 0 0 12.5 8h-9A1.5 1.5 0 0 0 2 9.5Z" />
								</svg>
								{dir}
							</button>
						{/each}
						{#if browserDirs.length === 0}
							<div class="text-center text-gray-400 dark:text-gray-500 py-4 text-xs">
								{$i18n.t('No subdirectories')}
							</div>
						{/if}
					</div>
				{/if}
			</div>

			<div class="flex justify-end gap-2 px-4 py-3 border-t border-gray-100 dark:border-gray-800">
				<button
					class="px-3 py-1.5 text-sm rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition"
					on:click={() => (showBrowser = false)}
				>
					{$i18n.t('Cancel')}
				</button>
				<button
					class="px-3 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-lg"
					on:click={selectBrowserPath}
				>
					{$i18n.t('Select This Directory')}
				</button>
			</div>
		</div>
	</div>
{/if}
