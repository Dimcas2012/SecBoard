////SecBoard\SecBoard\static\js\asset_table.js
//if (typeof AssetUtils === 'undefined') {
//    throw new Error('AssetUtils must be loaded before asset_table.js');
//}
//
//document.addEventListener('DOMContentLoaded', function() {
//    class AssetTable {
//        constructor() {
//            this.table = null;
//            this.criticalityLevels = null;
//            this.config = window.ASSET_CONFIG;
//            this.personnelManagement = {
//                selectedOwners: new Set(),
//                selectedAdmins: new Set(),
//                allOwners: [],
//                allAdmins: []
//            };
//
//            // Bind methods to ensure correct 'this' context
//            this.initializePersonnelSearch = this.initializePersonnelSearch.bind(this);
//            this.searchPersonnelList = this.searchPersonnelList.bind(this);
//            this.handlePersonnelSelection = this.handlePersonnelSelection.bind(this);
//            this.displayPersonnelList = this.displayPersonnelList.bind(this);
//            this.updateSelectedUsers = this.updateSelectedUsers.bind(this);
//            this.showEditModal = this.showEditModal.bind(this);
//            this.handleEdit = this.handleEdit.bind(this);
//
//            if (!this.config) {
//                throw new Error('ASSET_CONFIG must be defined before initializing AssetTable');
//            }
//
//            if (!this.checkApiUrls()) {
//                throw new Error('Required API URLs are not properly configured');
//            }
//
//            this.init();
//        }
//
//        async init() {
//            try {
//                await this.initializeComponents();
//                this.initializeTable();
//                this.bindEvents();
//                this.setupAjaxDefaults();
//            } catch (error) {
//                console.error('Error initializing AssetTable:', error);
//                AssetUtils.showNotification(this.config.translations.actions.error, 'danger');
//            }
//        }
//
//        checkApiUrls() {
//            const requiredUrls = [
//                'getAllAssetOwners',
//                'getAllAssetAdministrators'
//            ];
//            const missingUrls = requiredUrls.filter(url => !this.config.urls[url]);
//
//            if (missingUrls.length > 0) {
//                console.error('Missing required API URLs:', missingUrls);
//                return false;
//            }
//            console.log('API URLs configured:', this.config.urls);
//            return true;
//        }
//
//        async initializeComponents() {
//            try {
//                this.criticalityLevels = await AssetUtils.loadCriticalityLevels();
//                console.log('Loaded criticality levels:', this.criticalityLevels);
//
//                AssetUtils.initializeTooltips();
//                AssetUtils.initializeDatepickers();
//                AssetUtils.initializeSelects();
//                this.initializeCriticalityHandlers();
//            } catch (error) {
//                console.error('Error initializing components:', error);
//                throw error;
//            }
//        }
//
//        initializeCriticalityHandlers() {
//            ['editConfidentiality', 'editIntegrity', 'editAvailability'].forEach(selectId => {
//                $(`#${selectId}`).on('change', async () => {
//                    const baseId = selectId.replace('edit', '').toLowerCase();
//                    const value = $(`#${selectId}`).val();
//                    const $description = $(`#edit${baseId.charAt(0).toUpperCase() + baseId.slice(1)}Description`);
//                    const $color = $(`#edit${baseId.charAt(0).toUpperCase() + baseId.slice(1)}Color`);
//
//                    if (!value) {
//                        $description.hide();
//                        $color.hide();
//                        return;
//                    }
//
//                    try {
//                        const levels = await AssetUtils.loadCriticalityLevels();
//                        if (levels && levels[value]) {
//                            const levelData = levels[value];
//                            const descriptions = {
//                                confidentiality: levelData.description_confid,
//                                integrity: levelData.description_integ,
//                                availability: levelData.description_avail
//                            };
//                            $description.text(descriptions[baseId]).show();
//                            $color.css('background-color', levelData.color).show();
//                        }
//                    } catch (error) {
//                        console.error('Error loading criticality levels:', error);
//                    }
//                });
//            });
//        }
//
//        initializeTable() {
//            this.table = new DataTable('#assetTable', {
//                serverSide: true,
//                processing: true,
//                ajax: {
//                    url: this.config.urls.assetData,
//                    type: 'GET',
//                    data: (d) => ({
//                        ...d,
//                        showDeleted: $('#showDeletedAssets').is(':checked')
//                    }),
//                    dataSrc: (response) => {
//                        if (!response?.data?.length) {
//                            console.error('Invalid response format:', response);
//                            return [];
//                        }
//                        return response.data;
//                    }
//                },
//                columns: this.getColumnDefinitions(),
//                drawCallback: () => AssetUtils.initializeTooltips(),
//                language: this.config.translations.table,
//                pageLength: this.config.settings.pageLength,
//                scrollX: true,
//                autoWidth: false,
//                responsive: true,
//                order: [[0, 'desc']],
//                createdRow: (row, data) => {
//                    if (data.deletion_date) {
//                        $(row).addClass('deleted-asset');
//                        $('td', row).addClass('deleted-asset-cell');
//                    }
//                }
//            });
//        }
//
//        getColumnDefinitions() {
//            const baseColumns = [
//                {
//                    data: "asset_id",
//                    width: "100px",
//                    className: 'dt-body-center'
//                },
//                {
//                    data: "name",
//                    width: "150px"
//                },
//                {
//                    data: "company",
//                    width: "120px"
//                },
//                {
//                    data: "group",
//                    width: "150px"
//                },
//                {
//                    data: "description",
//                    width: "200px",
//                    render: (data, type) => {
//                        if (type === 'display') {
//                            const safeText = this.formatText(data);
//                            return this.renderTruncatedText(safeText, this.config.settings.truncateLength);
//                        }
//                        return data;
//                    }
//                },
//                {
//                    data: "location",
//                    width: "120px"
//                },
//                {
//                    data: "confidentiality",
//                    width: "130px",
//                    className: 'dt-body-center',
//                    render: (data, type) => {
//                        if (type === 'display' && data) {
//                            return `
//                                <span class="criticality-badge d-inline-block w-100 text-center"
//                                    style="background-color:${data.color};"
//                                    data-bs-toggle="tooltip"
//                                    title="${data.text}">
//                                    ${data.text}
//                                </span>`;
//                        }
//                        return data?.text || '';
//                    }
//                },
//                {
//                    data: "integrity",
//                    width: "130px",
//                    className: 'dt-body-center',
//                    render: (data, type) => {
//                        if (type === 'display' && data) {
//                            return `
//                                <span class="criticality-badge d-inline-block w-100 text-center"
//                                    style="background-color:${data.color};"
//                                    data-bs-toggle="tooltip"
//                                    title="${data.text}">
//                                    ${data.text}
//                                </span>`;
//                        }
//                        return data?.text || '';
//                    }
//                },
//                {
//                    data: "availability",
//                    width: "130px",
//                    className: 'dt-body-center',
//                    render: (data, type) => {
//                        if (type === 'display' && data) {
//                            return `
//                                <span class="criticality-badge d-inline-block w-100 text-center"
//                                    style="background-color:${data.color};"
//                                    data-bs-toggle="tooltip"
//                                    title="${data.text}">
//                                    ${data.text}
//                                </span>`;
//                        }
//                        return data?.text || '';
//                    }
//                },
//                {
//                    data: "registration_date",
//                    width: "120px",
//                    className: 'dt-body-center',
//                    render: (data, type) => {
//                        if (type === 'display') {
//                            return AssetUtils.formatDate(data);
//                        }
//                        return data;
//                    }
//                },
//                {
//                    data: "deletion_date",
//                    width: "120px",
//                    className: 'dt-body-center',
//                    render: (data, type) => {
//                        if (type === 'display') {
//                            return data ? AssetUtils.formatDate(data) : '';
//                        }
//                        return data;
//                    }
//                },
//                {
//                    data: "notes",
//                    width: "200px",
//                    render: (data, type) => {
//                        if (type === 'display') {
//                            return this.renderTruncatedText(data, this.config.settings.truncateLength);
//                        }
//                        return data;
//                    }
//                },
//                {
//                    data: "owners",
//                    width: "200px",
//                    render: (data, type) => {
//                        if (type === 'display' && data) {
//                            const owners = typeof data === 'string' ? JSON.parse(data) : data;
//                            return owners.map(owner => {
//                                const tooltipContent = `
//                                    Company: ${owner.company}<br>
//                                    Department: ${owner.department}<br>
//                                    Position: ${owner.position}<br>
//                                    Email: ${owner.email}<br>
//                                    Phone: ${owner.phone}
//                                `;
//                                return `
//                                    <span class="badge bg-info me-1"
//                                        data-bs-toggle="tooltip"
//                                        data-bs-html="true"
//                                        title="${tooltipContent}">
//                                        ${owner.name}
//                                    </span>`;
//                            }).join(' ');
//                        }
//                        return data;
//                    }
//                },
//                {
//                    data: "administrators",
//                    width: "200px",
//                    render: (data, type) => {
//                        if (type === 'display' && data) {
//                            const admins = typeof data === 'string' ? JSON.parse(data) : data;
//                            return admins.map(admin => {
//                                const tooltipContent = `
//                                    Company: ${admin.company}<br>
//                                    Department: ${admin.department}<br>
//                                    Position: ${admin.position}<br>
//                                    Email: ${admin.email}<br>
//                                    Phone: ${admin.phone}
//                                `;
//                                return `
//                                    <span class="badge bg-secondary me-1"
//                                        data-bs-toggle="tooltip"
//                                        data-bs-html="true"
//                                        title="${tooltipContent}">
//                                        ${admin.name}
//                                    </span>`;
//                            }).join(' ');
//                        }
//                        return data;
//                    }
//                },
//                {
//                    data: "last_modified",
//                    width: "150px",
//                    className: 'dt-body-center',
//                    render: (data, type) => {
//                        if (type === 'display' && data) {
//                            return `
//                                <span data-bs-toggle="tooltip"
//                                    title="Modified by: ${data.user}">
//                                    ${data.datetime}
//                                </span>`;
//                        }
//                        return data?.datetime || '';
//                    }
//                }
//            ];
//
//            if (window.ASSET_CONFIG.user.canEdit) {
//                baseColumns.push({
//                    data: "id",
//                    width: "100px",
//                    orderable: false,
//                    searchable: false,
//                    className: 'dt-body-center',
//                    render: (data, type) => {
//                        if (type === 'display') {
//                            return `
//                                <div class="btn-group" role="group">
//                                    <button class="btn btn-sm btn-primary edit-asset" data-id="${data}">
//                                        <i class="fas fa-edit"></i>
//                                    </button>
//                                    <button class="btn btn-sm btn-danger delete-asset" data-id="${data}">
//                                        <i class="fas fa-trash"></i>
//                                    </button>
//                                </div>
//                            `;
//                        }
//                        return data;
//                    }
//                });
//            }
//
//            return baseColumns;
//        }
//
//        renderTruncatedText(text, maxLength) {
//            if (!text) return '';
//            text = text.toString();
//            if (text.length <= maxLength) return text;
//
//            const truncated = text.substring(0, maxLength);
//            return `
//                <span class="text-truncate"
//                    data-bs-toggle="tooltip"
//                    title="${text.replace(/"/g, '&quot;')}">
//                    ${truncated}...
//                </span>`;
//        }
//
//        formatText(text) {
//            if (!text) return '';
//            return text.toString()
//                .replace(/&/g, '&amp;')
//                .replace(/</g, '&lt;')
//                .replace(/>/g, '&gt;')
//                .replace(/"/g, '&quot;')
//                .replace(/'/g, '&#039;');
//        }
//        async showEditModal(assetData) {
//            try {
//                // Basic fields setup
//                $('#assetId').val(assetData.id);
//                $('#editName').val(assetData.name);
//                $('#editCompany').val(assetData.company).trigger('change');
//                $('#editLocation').val(assetData.location);
//                $('#editDescription').val(assetData.description);
//                $('#editNotes').val(assetData.notes);
//
//                // Group/Type selection setup
//                const groupTypeValue = `${assetData.group},${assetData.asset_type}`;
//                const groupSection = $(`.group-header[data-group-id="${assetData.group}"]`).closest('.group-section');
//
//                // Reset all groups first
//                $('.group-section').each(function() {
//                    $(this).find('.group-description, .group-types').addClass('d-none');
//                    $(this).find('.fa-chevron-down').css('transform', '');
//                    $(this).find('.type-option').removeClass('selected-type');
//                    $(this).find('input[name="group_asset_type"]').prop('checked', false);
//                });
//
//                // Show selected group content
//                groupSection.find('.group-description, .group-types').removeClass('d-none');
//                groupSection.find('.fa-chevron-down').css('transform', 'rotate(180deg)');
//
//                // Select radio and update styles
//                const radio = $(`input[name="group_asset_type"][value="${groupTypeValue}"]`);
//                radio.prop('checked', true);
//                radio.closest('.type-option').addClass('selected-type');
//                $('#editGroupAssetType').val(groupTypeValue);
//
//                // Criticality levels
//                $('#editConfidentiality').val(assetData.confidentiality).trigger('change');
//                $('#editIntegrity').val(assetData.integrity).trigger('change');
//                $('#editAvailability').val(assetData.availability).trigger('change');
//
//                // Dates
//                if (assetData.registration_date) {
//                    $('#editRegistrationDate').datepicker('update', AssetUtils.formatDate(assetData.registration_date));
//                }
//                if (assetData.deletion_date) {
//                    $('#editDeletionDate').datepicker('update', AssetUtils.formatDate(assetData.deletion_date));
//                }
//
//                // Show modal first
//                const modalInstance = $('#editAssetModal');
//                modalInstance.modal('show');
//
//                // Initialize personnel containers
//                this.personnelManagement = {
//                    selectedOwners: new Set(assetData.owners?.map(owner => owner.id) || []),
//                    selectedAdmins: new Set(assetData.administrators?.map(admin => admin.id) || []),
//                    allOwners: [],
//                    allAdmins: []
//                };
//
//                // Reset containers
//                $('#editOwnerSearchResults, #editAdminSearchResults').empty();
//                $('#editSelectedOwners, #editSelectedAdmins').html(`
//                    <div class="text-muted text-center p-2">No users selected</div>
//                `);
//
//                if (assetData.company) {
//                    try {
//                        // Show loading state
//                        const loadingHtml = `
//                            <div class="text-center p-3">
//                                <div class="spinner-border spinner-border-sm text-primary"></div>
//                                <p class="mt-2">Loading users...</p>
//                            </div>
//                        `;
//                        $('#editOwnerSearchResults, #editAdminSearchResults').html(loadingHtml);
//
//                        // Load both lists concurrently
//                        const [owners, admins] = await Promise.all([
//                            $.ajax({
//                                url: this.config.urls.getAllAssetOwners,
//                                type: 'GET',
//                                data: { company_id: assetData.company }
//                            }),
//                            $.ajax({
//                                url: this.config.urls.getAllAssetAdministrators,
//                                type: 'GET',
//                                data: { company_id: assetData.company }
//                            })
//                        ]);
//
//                        // Store and display results
//                        this.personnelManagement.allOwners = owners;
//                        this.personnelManagement.allAdmins = admins;
//
//                        // Display lists
//                        this.displayPersonnelList('owner', owners);
//                        this.displayPersonnelList('admin', admins);
//
//                        // Update selected users
//                        this.updateSelectedUsers('owner', this.personnelManagement);
//                        this.updateSelectedUsers('admin', this.personnelManagement);
//
//                        // Initialize search functionality
//                        if (typeof this.initializePersonnelSearch === 'function') {
//                            this.initializePersonnelSearch();
//                        } else {
//                            console.error('initializePersonnelSearch is not defined');
//                        }
//
//                    } catch (error) {
//                        console.error('Failed to load personnel:', error);
//                        const errorHtml = `
//                            <div class="text-center p-3 text-danger">
//                                <i class="fas fa-exclamation-circle mb-2"></i>
//                                <p>Error loading users</p>
//                                <button class="btn btn-sm btn-outline-primary reload-personnel">
//                                    <i class="fas fa-sync-alt me-1"></i> Retry
//                                </button>
//                            </div>
//                        `;
//                        $('#editOwnerSearchResults, #editAdminSearchResults').html(errorHtml);
//
//                        // Add retry handler
//                        $('.reload-personnel').on('click', () => this.showEditModal(assetData));
//                    }
//                }
//
//                modalInstance.one('shown.bs.modal', () => {
//                    $('[data-bs-toggle="tooltip"]').tooltip();
//                    $('.select2-container').css('z-index', '1056');
//                });
//
//            } catch (error) {
//                console.error('Error in showEditModal:', error);
//                AssetUtils.showNotification('Error loading asset details', 'danger');
//            }
//        }
//        async handleEdit(e) {
//            const assetId = $(e.currentTarget).data('id');
//            if (!assetId) {
//                console.error('No asset ID provided for edit');
//                return;
//            }
//
//            AssetUtils.showLoading();
//            try {
//                const assetData = await this.loadAssetData(assetId);
//                await this.showEditModal(assetData);
//            } catch (error) {
//                console.error('Error handling edit:', error);
//                AssetUtils.showNotification(this.config.translations.actions.error, 'danger');
//            } finally {
//                AssetUtils.hideLoading();
//            }
//        }
//
//        async loadAssetData(assetId) {
//            try {
//                return await $.ajax({
//                    url: this.config.urls.getAsset.replace('0', assetId),
//                    type: 'GET'
//                });
//            } catch (error) {
//                console.error('Error loading asset data:', error);
//                throw error;
//            }
//        }
//
//        searchPersonnelList(type, query) {
//            // Get users from the stored data in personnelManagement
//            const users = type === 'owner'
//                ? this.personnelManagement.allOwners
//                : this.personnelManagement.allAdmins;
//
//            if (!users) {
//                console.warn(`No ${type}s data available`);
//                this.displayPersonnelList(type, [], query);
//                return;
//            }
//
//            // Filter users based on search query
//            const filtered = query ? users.filter(user => {
//                if (!user) return false;
//                const searchText = query.toLowerCase();
//                const userData = {
//                    name: (user.name || '').toLowerCase(),
//                    department: (user.department || '').toLowerCase(),
//                    position: (user.position || '').toLowerCase(),
//                    email: (user.email || '').toLowerCase()
//                };
//                return Object.values(userData).some(value => value.includes(searchText));
//            }) : users;
//
//            this.displayPersonnelList(type, filtered, query);
//        }
//
//        displayPersonnelList(type, users, query = '') {
//            console.log('displayPersonnelList input:', { type, users, query });
//
//            const resultsContainer = $(`#edit${type.charAt(0).toUpperCase() + type.slice(1)}SearchResults`);
//            const selectedSet = type === 'owner' ? this.personnelManagement.selectedOwners : this.personnelManagement.selectedAdmins;
//
//            // Ensure users is always an array
//            let usersArray = [];
//            try {
//                if (users) {
//                    if (Array.isArray(users)) {
//                        usersArray = users;
//                    } else if (typeof users === 'string') {
//                        usersArray = JSON.parse(users);
//                    } else if (typeof users === 'object') {
//                        if (users.data) {
//                            usersArray = Array.isArray(users.data) ? users.data : [users.data];
//                        } else {
//                            usersArray = Object.values(users);
//                        }
//                    }
//                }
//            } catch (error) {
//                console.error('Error normalizing users:', error);
//            }
//
//            console.log('Normalized users array:', usersArray);
//
//            if (!usersArray.length) {
//                resultsContainer.html(`
//                    <div class="text-center p-3 text-muted">
//                        <i class="fas fa-users fa-2x mb-2"></i>
//                        <p>${query ? 'No matching users found' : `No ${type}s available`}</p>
//                    </div>
//                `);
//                return;
//            }
//
//            const html = usersArray.map(user => {
//                if (!user) return '';
//                const userId = user.id || user.cabinet_user_id;
//                const isSelected = selectedSet.has(userId);
//                const userData = {
//                    name: user.name || user.user?.get_full_name || 'Unknown User',
//                    department: user.department || '',
//                    position: user.position || '',
//                    email: user.email || user.user?.email || ''
//                };
//
//                return `
//                    <div class="user-result p-2 border-bottom ${isSelected ? 'selected-user' : ''}"
//                         data-user='${JSON.stringify(user)}'
//                         data-type="${type}"
//                         data-user-id="${userId}">
//                        <div class="d-flex justify-content-between align-items-center">
//                            <div class="flex-grow-1">
//                                <div class="fw-bold">${userData.name}</div>
//                                ${userData.department || userData.position ? `
//                                    <div class="small text-muted">
//                                        ${userData.department ?
//                                            `<span class="badge bg-secondary me-1">${userData.department}</span>` : ''}
//                                        ${userData.position ?
//                                            `<span class="badge bg-info">${userData.position}</span>` : ''}
//                                    </div>
//                                ` : ''}
//                                ${userData.email ? `<div class="small text-muted">${userData.email}</div>` : ''}
//                            </div>
//                            <div class="select-indicator ms-2">
//                                <i class="fas ${isSelected ? 'fa-check-circle text-success' : 'fa-circle text-muted'} fs-5"></i>
//                            </div>
//                        </div>
//                    </div>
//                `;
//            }).join('');
//
//            resultsContainer.html(html);
//        }
//
//        updateSelectedUsers(type, personnelData) {
//            const container = $(`#editSelected${type === 'owner' ? 'Owners' : 'Admins'}`);
//            const users = type === 'owner' ? personnelData.allOwners : personnelData.allAdmins;
//            const selectedSet = type === 'owner' ? personnelData.selectedOwners : personnelData.selectedAdmins;
//
//            if (!selectedSet?.size) {
//                container.html('<div class="text-muted text-center p-2">No users selected</div>');
//                return;
//            }
//
//            const html = Array.from(selectedSet).map(id => {
//                const user = users.find(u => u.id === id || u.cabinet_user_id === id);
//                if (!user) return null;
//
//                return `
//                    <div class="selected-user-item p-2 border-bottom">
//                        <div class="d-flex justify-content-between align-items-center">
//                            <div>
//                                <div class="fw-bold">${user.name}</div>
//                                ${user.department || user.position ? `
//                                    <div class="small text-muted">
//                                        ${user.department ?
//                                            `<span class="badge bg-secondary me-1">${user.department}</span>` : ''}
//                                        ${user.position ?
//                                            `<span class="badge bg-info">${user.position}</span>` : ''}
//                                    </div>
//                                ` : ''}
//                                ${user.email ? `<div class="small text-muted">${user.email}</div>` : ''}
//                            </div>
//                            <button type="button" class="btn btn-sm btn-outline-danger remove-selected-user"
//                                    data-type="${type}" data-id="${user.id || user.cabinet_user_id}">
//                                <i class="fas fa-times"></i>
//                            </button>
//                        </div>
//                    </div>
//                `;
//            }).filter(Boolean).join('');
//
//            container.html(html || '<div class="text-muted text-center p-2">No users selected</div>');
//        }
//
//        handlePersonnelSelection(e) {
//            const $target = $(e.currentTarget);
//            const type = $target.data('type');
//            const userId = $target.data('user-id');
//            const selectedSet = this.personnelManagement[type === 'owner' ? 'selectedOwners' : 'selectedAdmins'];
//
//            if (selectedSet.has(userId)) {
//                selectedSet.delete(userId);
//                $target.removeClass('selected-user')
//                    .find('.select-indicator i')
//                    .removeClass('fa-check-circle text-success')
//                    .addClass('fa-circle text-muted');
//            } else {
//                selectedSet.add(userId);
//                $target.addClass('selected-user')
//                    .find('.select-indicator i')
//                    .removeClass('fa-circle text-muted')
//                    .addClass('fa-check-circle text-success');
//            }
//
//            this.updateSelectedUsers(type, this.personnelManagement);
//        }
//
//        initializePersonnelSearch() {
//            // Clear previous event handlers
//            $('#editOwnerSearchInput, #editAdminSearchInput').off('input');
//            $('#editOwnerSearchResults, #editAdminSearchResults').off('click', '.user-result');
//
//            // Setup owner search
//            $('#editOwnerSearchInput').on('input', this.debounce((e) => {
//                console.log('Searching owners:', e.target.value);
//                this.searchPersonnelList('owner', e.target.value);
//            }, 300));
//
//            // Setup admin search
//            $('#editAdminSearchInput').on('input', this.debounce((e) => {
//                console.log('Searching admins:', e.target.value);
//                this.searchPersonnelList('admin', e.target.value);
//            }, 300));
//
//            // Setup selection handlers with proper event delegation
//            $('#editOwnerSearchResults, #editAdminSearchResults').on('click', '.user-result', (e) => {
//                console.log('User result clicked');
//                this.handlePersonnelSelection(e);
//            });
//
//            console.log('Personnel search initialized');
//        }
//
//        debounce(func, wait) {
//            let timeout;
//            return (...args) => {
//                clearTimeout(timeout);
//                timeout = setTimeout(() => func.apply(this, args), wait);
//            };
//        }
//
//        bindEvents() {
//            // Table events
//            $('#showDeletedAssets').on('change', () => this.table.ajax.reload());
//            $('#assetTable').on('click', '.edit-asset', e => this.handleEdit(e));
//            $('#assetTable').on('click', '.delete-asset', e => this.handleDelete(e));
//            $('#exportExcelBtn').on('click', () => this.handleExport());
//
//            // Modal events
//            const modalInstance = $('#editAssetModal');
//
//            modalInstance.on('shown.bs.modal', () => {
//                AssetUtils.initializeTooltips();
//                $('.select2-container').css('z-index', '1056');
//                this.initializePersonnelSearch();
//            });
//
//            modalInstance.on('hidden.bs.modal', () => {
//                AssetUtils.clearValidationErrors();
//                this.personnelManagement = {
//                    selectedOwners: new Set(),
//                    selectedAdmins: new Set(),
//                    allOwners: [],
//                    allAdmins: []
//                };
//            });
//
//            // Company change handler
//            $('#editCompany').on('change', async (e) => {
//                const companyId = $(e.target).val();
//                if (companyId) {
//                    this.personnelManagement.selectedOwners.clear();
//                    this.personnelManagement.selectedAdmins.clear();
//
//                    try {
//                        const [owners, admins] = await Promise.all([
//                            $.ajax({
//                                url: this.config.urls.getAllAssetOwners,
//                                type: 'GET',
//                                data: { company_id: companyId }
//                            }),
//                            $.ajax({
//                                url: this.config.urls.getAllAssetAdministrators,
//                                type: 'GET',
//                                data: { company_id: companyId }
//                            })
//                        ]);
//
//                        this.personnelManagement.allOwners = owners;
//                        this.personnelManagement.allAdmins = admins;
//
//                        this.displayPersonnelList('owner', owners);
//                        this.displayPersonnelList('admin', admins);
//
//                        this.updateSelectedUsers('owner', this.personnelManagement);
//                        this.updateSelectedUsers('admin', this.personnelManagement);
//                    } catch (error) {
//                        console.error('Error loading personnel:', error);
//                        AssetUtils.showNotification('Error loading personnel data', 'danger');
//                    }
//                } else {
//                    $('#editOwnerSearchResults, #editAdminSearchResults').empty();
//                    $('#editSelectedOwners, #editSelectedAdmins')
//                        .html('<div class="text-muted text-center p-2">No users selected</div>');
//                }
//            });
//        }
//
//        setupAjaxDefaults() {
//            const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
//            $.ajaxSetup({
//                headers: {
//                    'X-CSRFToken': csrftoken
//                },
//                beforeSend: () => AssetUtils.showLoading(),
//                complete: () => AssetUtils.hideLoading()
//            });
//        }
//    }
//
//    // Initialize the AssetTable when document is ready
//    window.assetTable = new AssetTable();
//});
