/**
 * Acceptable Risk Management JavaScript
 * Handles the Acceptable Risk configuration functionality
 */

class AcceptableRiskManager {
    constructor() {
        this.table = null;
        this.modal = null;
        this.referenceData = null;
        this.currentLanguage = window.currentLanguage || 'uk';
        
        this.init();
    }
    
    init() {
        this.initTable();
        this.initModal();
        this.bindEvents();
        this.loadReferenceData();
    }
    
    initTable() {
        if ($('#acceptableRiskTable').length === 0) return;
        
        this.table = $('#acceptableRiskTable').DataTable({
            "processing": true,
            "serverSide": false,
            "ajax": {
                "url": "/app_risk/acceptable-risk/data/",
                "type": "GET",
                "data": function(d) {
                    d.language = this.currentLanguage;
                }.bind(this)
            },
            "columns": [
                {
                    "data": null,
                    "defaultContent": '',
                    "orderable": false,
                    "searchable": false,
                    "className": 'select-checkbox'
                },
                {"data": "company"},
                {"data": "asset_group"},
                {
                    "data": "criticality_level",
                    "render": function(data, type, row) {
                        if (type === 'display') {
                            return '<span class="impact-text" style="color: ' + row.criticality_color + ';">' + data + '</span>';
                        }
                        return data;
                    }
                },
                {
                    "data": "acceptable_risk_level",
                    "render": function(data, type, row) {
                        if (type === 'display') {
                            return '<span class="impact-text" style="color: ' + row.acceptable_risk_color + ';">' + data + '</span>';
                        }
                        return data;
                    }
                },
                {"data": "created_at"},
                {"data": "updated_at"},
                {
                    "data": null,
                    "orderable": false,
                    "searchable": false,
                    "render": function(data, type, row) {
                        return '<div class="btn-group btn-group-sm">' +
                               '<button class="btn btn-outline-primary edit-acceptable-risk" data-id="' + row.id + '" title="Edit">' +
                               '<i class="fas fa-edit"></i></button>' +
                               '<button class="btn btn-outline-danger delete-acceptable-risk" data-id="' + row.id + '" title="Delete">' +
                               '<i class="fas fa-trash"></i></button>' +
                               '</div>';
                    }
                }
            ],
            "language": {
                "processing": "Loading...",
                "search": "Search:",
                "lengthMenu": "Show _MENU_ entries",
                "info": "Showing _START_ to _END_ of _TOTAL_ entries",
                "infoEmpty": "Showing 0 to 0 of 0 entries",
                "infoFiltered": "(filtered from _MAX_ total entries)",
                "emptyTable": "No data available in table",
                "zeroRecords": "No matching records found"
            },
            "order": [[1, 'asc']],
            "pageLength": 25,
            "select": {
                'style': 'multi',
                'selector': 'td:first-child'
            }
        });
    }
    
    initModal() {
        this.modal = new bootstrap.Modal(document.getElementById('acceptableRiskModal'));
    }
    
    bindEvents() {
        // Add new button
        $(document).on('click', '#addAcceptableRiskBtn', () => {
            this.showModal();
        });
        
        // Save button
        $(document).on('click', '#saveAcceptableRiskBtn', () => {
            this.saveAcceptableRisk();
        });
        
        // Edit button
        $(document).on('click', '.edit-acceptable-risk', (e) => {
            const id = $(e.currentTarget).data('id');
            this.editAcceptableRisk(id);
        });
        
        // Delete button
        $(document).on('click', '.delete-acceptable-risk', (e) => {
            const id = $(e.currentTarget).data('id');
            this.deleteAcceptableRisk(id);
        });
        
        // Select all checkbox
        $(document).on('click', '#selectAllAcceptableRisk', (e) => {
            if (e.target.checked) {
                this.table.rows().select();
            } else {
                this.table.rows().deselect();
            }
        });
        
        // Export button
        $(document).on('click', '#exportAcceptableRiskBtn', () => {
            this.exportAcceptableRisk();
        });
        
        // Modal events
        $('#acceptableRiskModal').on('hidden.bs.modal', () => {
            this.resetForm();
        });
    }
    
    loadReferenceData() {
        $.get('/app_risk/acceptable-risk/reference-data/')
            .done((data) => {
                this.referenceData = data;
                this.populateSelects();
            })
            .fail((xhr, status, error) => {
                console.error('Error loading reference data:', error);
                this.showAlert('error', 'Error loading reference data');
            });
    }
    
    populateSelects() {
        if (!this.referenceData) return;
        
        // Populate company select
        const companySelect = $('#acceptable-risk-company');
        companySelect.empty().append('<option value="">Select Company</option>');
        this.referenceData.companies.forEach(company => {
            companySelect.append(`<option value="${company.id}">${company.name}</option>`);
        });
        
        // Populate asset group select
        const assetGroupSelect = $('#acceptable-risk-asset-group');
        assetGroupSelect.empty().append('<option value="">Select Asset Group</option>');
        this.referenceData.asset_groups.forEach(group => {
            assetGroupSelect.append(`<option value="${group.id}">${group.name}</option>`);
        });
        
        // Populate criticality level select
        const criticalitySelect = $('#acceptable-risk-criticality');
        criticalitySelect.empty().append('<option value="">Select Criticality Level</option>');
        this.referenceData.criticality_levels.forEach(level => {
            criticalitySelect.append(`<option value="${level.id}">${level.name} (Cost: ${level.cost})</option>`);
        });
        
        // Populate risk level select
        const riskLevelSelect = $('#acceptable-risk-level');
        riskLevelSelect.empty().append('<option value="">Select Risk Level</option>');
        this.referenceData.risk_levels.forEach(level => {
            riskLevelSelect.append(`<option value="${level.id}">${level.name}</option>`);
        });
    }
    
    showModal(data = null) {
        if (data) {
            // Edit mode
            $('#acceptable-risk-id').val(data.id);
            $('#acceptable-risk-company').val(data.company_id);
            $('#acceptable-risk-asset-group').val(data.asset_group_id);
            $('#acceptable-risk-criticality').val(data.criticality_level_id);
            $('#acceptable-risk-level').val(data.acceptable_risk_level_id);
            $('#acceptableRiskModalLabel').html('<i class="fas fa-edit me-2"></i>Edit Acceptable Risk Settings');
        } else {
            // Add mode
            this.resetForm();
            $('#acceptableRiskModalLabel').html('<i class="fas fa-plus me-2"></i>Add Acceptable Risk Settings');
        }
        
        this.modal.show();
    }
    
    resetForm() {
        $('#acceptable-risk-id').val('');
        $('#acceptable-risk-company').val('');
        $('#acceptable-risk-asset-group').val('');
        $('#acceptable-risk-criticality').val('');
        $('#acceptable-risk-level').val('');
        $('#acceptableRiskForm')[0].reset();
    }
    
    saveAcceptableRisk() {
        const formData = {
            company_id: $('#acceptable-risk-company').val(),
            asset_group_id: $('#acceptable-risk-asset-group').val(),
            criticality_level_id: $('#acceptable-risk-criticality').val(),
            acceptable_risk_level_id: $('#acceptable-risk-level').val()
        };
        
        // Validate required fields
        if (!formData.company_id || !formData.asset_group_id || 
            !formData.criticality_level_id || !formData.acceptable_risk_level_id) {
            this.showAlert('warning', 'Please fill in all required fields');
            return;
        }
        
        const id = $('#acceptable-risk-id').val();
        const url = id ? `/app_risk/acceptable-risk/save/` : `/app_risk/acceptable-risk/save/`;
        
        $.ajax({
            url: url,
            type: 'POST',
            data: JSON.stringify(formData),
            contentType: 'application/json',
            headers: {
                'X-CSRFToken': $('[name=csrfmiddlewaretoken]').val()
            }
        })
        .done((response) => {
            if (response.status === 'success') {
                this.showAlert('success', response.message);
                this.modal.hide();
                this.table.ajax.reload();
            } else {
                this.showAlert('error', response.message);
            }
        })
        .fail((xhr, status, error) => {
            console.error('Error saving acceptable risk:', error);
            this.showAlert('error', 'Error saving acceptable risk settings');
        });
    }
    
    editAcceptableRisk(id) {
        // Find the row data
        const rowData = this.table.row(`[data-id="${id}"]`).data();
        if (rowData) {
            this.showModal(rowData);
        } else {
            this.showAlert('error', 'Could not find acceptable risk data');
        }
    }
    
    deleteAcceptableRisk(id) {
        if (confirm('Are you sure you want to delete this acceptable risk setting?')) {
            $.ajax({
                url: `/app_risk/acceptable-risk/delete/${id}/`,
                type: 'POST',
                headers: {
                    'X-CSRFToken': $('[name=csrfmiddlewaretoken]').val()
                }
            })
            .done((response) => {
                if (response.status === 'success') {
                    this.showAlert('success', response.message);
                    this.table.ajax.reload();
                } else {
                    this.showAlert('error', response.message);
                }
            })
            .fail((xhr, status, error) => {
                console.error('Error deleting acceptable risk:', error);
                this.showAlert('error', 'Error deleting acceptable risk setting');
            });
        }
    }
    
    exportAcceptableRisk() {
        const selectedRows = this.table.rows({selected: true}).data();
        if (selectedRows.length === 0) {
            this.showAlert('warning', 'Please select at least one row to export');
            return;
        }
        
        const ids = Array.from(selectedRows).map(row => row.id);
        window.location.href = `/app_risk/acceptable-risk/export/?ids=${ids.join(',')}`;
    }
    
    showAlert(type, message) {
        const alertClass = type === 'success' ? 'alert-success' :
                          type === 'error' ? 'alert-danger' :
                          type === 'warning' ? 'alert-warning' : 'alert-info';
        
        const icon = type === 'success' ? 'fas fa-check-circle' :
                    type === 'error' ? 'fas fa-exclamation-circle' :
                    type === 'warning' ? 'fas fa-exclamation-triangle' : 'fas fa-info-circle';
        
        const alertHtml = `
            <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
                <i class="${icon} me-2"></i>${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
        
        $('#alertContainer').append(alertHtml);
        
        // Remove the alert after 5 seconds
        setTimeout(() => {
            $('#alertContainer .alert:first-child').alert('close');
        }, 5000);
    }
}

// Initialize when document is ready
$(document).ready(function() {
    if ($('#acceptableRiskTab').length > 0) {
        window.acceptableRiskManager = new AcceptableRiskManager();
    }
});
