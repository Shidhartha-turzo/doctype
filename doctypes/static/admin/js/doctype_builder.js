/**
 * Doctype Field Builder - Interactive Visual Schema Editor
 * Allows drag-and-drop field management without editing raw JSON
 */

(function() {
    'use strict';

    // State management
    let fields = [];
    let editingFieldIndex = null;
    let draggedElement = null;

    // Initialize immediately or on page load
    function initialize() {
        console.log('Doctype Field Builder initializing...');
        console.log('window.doctypeFields:', window.doctypeFields);
        console.log('window.fieldTypes:', window.fieldTypes);
        console.log('window.childDoctypes:', window.childDoctypes);
        console.log('window.allDoctypes:', window.allDoctypes);
        initFieldBuilder();
        attachEventListeners();
        console.log('Doctype Field Builder initialized with', fields.length, 'fields');
    }

    // Run initialization when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        // DOM already loaded, initialize immediately
        initialize();
    }

    function initFieldBuilder() {
        // Load existing fields from Django context
        if (window.doctypeFields && Array.isArray(window.doctypeFields)) {
            fields = window.doctypeFields;
        }

        // Initialize schema field with empty fields array if empty
        const schemaField = document.getElementById('id_schema');
        if (schemaField && !schemaField.value.trim()) {
            schemaField.value = JSON.stringify({fields: []}, null, 2);
        }

        // Populate doctype dropdowns
        populateDoctypeDropdowns();

        // Render fields
        renderFields();

        // Update hidden schema field
        updateSchemaField();
    }

    function populateDoctypeDropdowns() {
        console.log('Populating doctype dropdowns...');
        console.log('All Doctypes:', window.allDoctypes);
        console.log('Child Doctypes:', window.childDoctypes);

        // Populate link doctype dropdown with all doctypes
        const linkDoctypeSelect = document.getElementById('link-doctype');
        if (linkDoctypeSelect && window.allDoctypes) {
            linkDoctypeSelect.innerHTML = '<option value="">-- Select Doctype --</option>';
            window.allDoctypes.forEach(doctype => {
                const option = document.createElement('option');
                option.value = doctype;
                option.textContent = doctype;
                linkDoctypeSelect.appendChild(option);
            });
            console.log(`Link doctype dropdown populated with ${window.allDoctypes.length} options`);
        }

        // Populate child doctype dropdown with only child doctypes
        const childDoctypeSelect = document.getElementById('child-doctype');
        if (childDoctypeSelect && window.childDoctypes) {
            childDoctypeSelect.innerHTML = '<option value="">-- Select Child Doctype --</option>';
            if (window.childDoctypes.length === 0) {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = '(No child doctypes available - create one first)';
                option.disabled = true;
                childDoctypeSelect.appendChild(option);
                console.log('Child doctype dropdown: No child doctypes available');
            } else {
                window.childDoctypes.forEach(doctype => {
                    const option = document.createElement('option');
                    option.value = doctype;
                    option.textContent = doctype;
                    childDoctypeSelect.appendChild(option);
                });
                console.log(`Child doctype dropdown populated with ${window.childDoctypes.length} options:`, window.childDoctypes);
            }
        }
    }

    function attachEventListeners() {
        console.log('Attaching event listeners...');

        // Add Field button
        const addFieldBtn = document.getElementById('add-field-btn');
        console.log('Add Field button:', addFieldBtn);
        if (addFieldBtn) {
            addFieldBtn.addEventListener('click', () => {
                console.log('Add Field button clicked!');
                openFieldModal();
            });
        } else {
            console.error('Add Field button not found!');
        }

        // Import JSON button
        const importJsonBtn = document.getElementById('import-json-btn');
        if (importJsonBtn) {
            importJsonBtn.addEventListener('click', importJSON);
        }

        // Export JSON button
        const exportJsonBtn = document.getElementById('export-json-btn');
        if (exportJsonBtn) {
            exportJsonBtn.addEventListener('click', exportJSON);
        }

        // Modal close button
        const closeModalBtn = document.getElementById('close-modal-btn');
        if (closeModalBtn) {
            closeModalBtn.addEventListener('click', closeFieldModal);
        }

        // Cancel button
        const cancelBtn = document.getElementById('cancel-btn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', closeFieldModal);
        }

        // Save field button
        const saveFieldBtn = document.getElementById('save-field-btn');
        if (saveFieldBtn) {
            saveFieldBtn.addEventListener('click', saveField);
        }

        // Field type change - show/hide type-specific options
        const fieldTypeSelect = document.getElementById('field-type');
        if (fieldTypeSelect) {
            fieldTypeSelect.addEventListener('change', handleFieldTypeChange);
        }

        // Close modal on background click
        const modal = document.getElementById('field-editor-modal');
        if (modal) {
            modal.addEventListener('click', function(e) {
                if (e.target === modal) {
                    closeFieldModal();
                }
            });
        }

        // Intercept form submission to ensure schema is updated
        const djangoForm = document.querySelector('form');
        if (djangoForm) {
            djangoForm.addEventListener('submit', function(e) {
                updateSchemaField();
            });
        }
    }

    function renderFields() {
        const fieldsList = document.getElementById('fields-list');
        const noFieldsMessage = document.getElementById('no-fields-message');

        if (!fieldsList) return;

        // Clear existing fields
        fieldsList.innerHTML = '';

        if (fields.length === 0) {
            if (noFieldsMessage) {
                noFieldsMessage.style.display = 'block';
            }
            return;
        }

        if (noFieldsMessage) {
            noFieldsMessage.style.display = 'none';
        }

        fields.forEach((field, index) => {
            const fieldItem = createFieldElement(field, index);
            fieldsList.appendChild(fieldItem);
        });
    }

    function createFieldElement(field, index) {
        const div = document.createElement('div');
        div.className = 'field-item';
        div.draggable = true;
        div.dataset.index = index;

        // Add drag event listeners
        div.addEventListener('dragstart', handleDragStart);
        div.addEventListener('dragover', handleDragOver);
        div.addEventListener('drop', handleDrop);
        div.addEventListener('dragend', handleDragEnd);

        // Field info section
        const fieldInfo = document.createElement('div');
        fieldInfo.className = 'field-info';

        // Field header (name + type badge)
        const fieldHeader = document.createElement('div');
        fieldHeader.className = 'field-header';

        const fieldName = document.createElement('span');
        fieldName.className = 'field-name';
        fieldName.textContent = field.label || field.name;

        const fieldTypeBadge = document.createElement('span');
        fieldTypeBadge.className = 'field-type-badge';
        fieldTypeBadge.setAttribute('data-type', field.type);
        fieldTypeBadge.textContent = (field.type || 'string').toUpperCase();

        fieldHeader.appendChild(fieldName);
        fieldHeader.appendChild(fieldTypeBadge);

        // Field badges (required, unique, readonly)
        const fieldBadges = document.createElement('div');
        fieldBadges.className = 'field-badges';

        if (field.required) {
            const badge = document.createElement('span');
            badge.className = 'field-badge required';
            badge.textContent = 'Required';
            fieldBadges.appendChild(badge);
        }

        if (field.unique) {
            const badge = document.createElement('span');
            badge.className = 'field-badge unique';
            badge.textContent = 'Unique';
            fieldBadges.appendChild(badge);
        }

        if (field.readonly) {
            const badge = document.createElement('span');
            badge.className = 'field-badge readonly';
            badge.textContent = 'Read Only';
            fieldBadges.appendChild(badge);
        }

        // Field details (description, default, options)
        const fieldDetails = document.createElement('div');
        fieldDetails.className = 'field-details';
        const detailsParts = [];

        if (field.description) {
            detailsParts.push(field.description);
        }

        if (field.default) {
            detailsParts.push(`Default: ${field.default}`);
        }

        if (field.type === 'link' && field.link_doctype) {
            detailsParts.push(`Links to: ${field.link_doctype}`);
        }

        if (field.type === 'select' && field.options) {
            const opts = Array.isArray(field.options) ? field.options.join(', ') : field.options;
            detailsParts.push(`Options: ${opts}`);
        }

        if (field.type === 'table' && field.child_doctype) {
            detailsParts.push(`Child: ${field.child_doctype}`);
        }

        if (field.type === 'computed' && field.formula) {
            detailsParts.push(`Formula: ${field.formula}`);
        }

        fieldDetails.textContent = detailsParts.join(' • ');

        fieldInfo.appendChild(fieldHeader);
        fieldInfo.appendChild(fieldBadges);
        if (detailsParts.length > 0) {
            fieldInfo.appendChild(fieldDetails);
        }

        // Field actions section
        const fieldActions = document.createElement('div');
        fieldActions.className = 'field-actions';

        // Move handle
        const moveBtn = document.createElement('button');
        moveBtn.type = 'button';
        moveBtn.className = 'move-handle';
        moveBtn.textContent = '⋮⋮';
        moveBtn.title = 'Drag to reorder';

        // Edit button
        const editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'edit-btn';
        editBtn.textContent = 'Edit';
        editBtn.addEventListener('click', () => editField(index));

        // Delete button
        const deleteBtn = document.createElement('button');
        deleteBtn.type = 'button';
        deleteBtn.className = 'delete-btn';
        deleteBtn.textContent = 'Delete';
        deleteBtn.addEventListener('click', () => deleteField(index));

        fieldActions.appendChild(moveBtn);
        fieldActions.appendChild(editBtn);
        fieldActions.appendChild(deleteBtn);

        div.appendChild(fieldInfo);
        div.appendChild(fieldActions);

        return div;
    }

    // Drag and Drop handlers
    function handleDragStart(e) {
        draggedElement = this;
        this.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/html', this.innerHTML);
    }

    function handleDragOver(e) {
        if (e.preventDefault) {
            e.preventDefault();
        }
        e.dataTransfer.dropEffect = 'move';
        return false;
    }

    function handleDrop(e) {
        if (e.stopPropagation) {
            e.stopPropagation();
        }

        if (draggedElement !== this) {
            const fromIndex = parseInt(draggedElement.dataset.index);
            const toIndex = parseInt(this.dataset.index);

            // Reorder fields array
            const movedField = fields.splice(fromIndex, 1)[0];
            fields.splice(toIndex, 0, movedField);

            // Re-render
            renderFields();
            updateSchemaField();
        }

        return false;
    }

    function handleDragEnd(e) {
        this.classList.remove('dragging');
    }

    // Modal operations
    function openFieldModal(fieldData = null, index = null) {
        console.log('openFieldModal called');
        const modal = document.getElementById('field-editor-modal');
        const modalTitle = document.getElementById('modal-title');
        const formContainer = document.getElementById('field-form');

        console.log('Modal element:', modal);
        console.log('Form container element:', formContainer);

        if (!modal || !formContainer) {
            console.error('Modal or form container not found!', {modal, formContainer});
            return;
        }

        // Reset all form fields manually
        document.getElementById('field-name').value = '';
        document.getElementById('field-label').value = '';
        document.getElementById('field-type').value = 'string';
        document.getElementById('field-default').value = '';
        document.getElementById('field-required').checked = false;
        document.getElementById('field-unique').checked = false;
        document.getElementById('field-readonly').checked = false;
        document.getElementById('field-description').value = '';
        document.getElementById('link-doctype').value = '';
        document.getElementById('select-options-input').value = '';
        document.getElementById('child-doctype').value = '';
        document.getElementById('formula').value = '';

        // Set modal title
        if (modalTitle) {
            modalTitle.textContent = fieldData ? 'Edit Field' : 'Add Field';
        }

        // Store editing index
        editingFieldIndex = index;

        // Populate form if editing
        if (fieldData) {
            document.getElementById('field-name').value = fieldData.name || '';
            document.getElementById('field-label').value = fieldData.label || '';
            document.getElementById('field-type').value = fieldData.type || 'string';
            document.getElementById('field-default').value = fieldData.default || '';
            document.getElementById('field-required').checked = fieldData.required || false;
            document.getElementById('field-unique').checked = fieldData.unique || false;
            document.getElementById('field-readonly').checked = fieldData.readonly || false;
            document.getElementById('field-description').value = fieldData.description || '';

            // Type-specific fields
            if (fieldData.link_doctype) {
                // Wait for next tick to ensure dropdown is populated
                setTimeout(() => {
                    document.getElementById('link-doctype').value = fieldData.link_doctype;
                }, 0);
            }
            if (fieldData.options) {
                const opts = Array.isArray(fieldData.options) ? fieldData.options.join(', ') : fieldData.options;
                document.getElementById('select-options-input').value = opts;
            }
            if (fieldData.child_doctype) {
                // Wait for next tick to ensure dropdown is populated
                setTimeout(() => {
                    document.getElementById('child-doctype').value = fieldData.child_doctype;
                }, 0);
            }
            if (fieldData.formula) {
                document.getElementById('formula').value = fieldData.formula;
            }
        }

        // Update type-specific options visibility
        handleFieldTypeChange();

        // Show modal
        modal.style.display = 'flex';
    }

    function closeFieldModal() {
        const modal = document.getElementById('field-editor-modal');
        if (modal) {
            modal.style.display = 'none';
        }
        editingFieldIndex = null;
    }

    function handleFieldTypeChange() {
        const fieldType = document.getElementById('field-type').value;

        // Hide all type-specific options
        document.getElementById('link-options').style.display = 'none';
        document.getElementById('select-options').style.display = 'none';
        document.getElementById('table-options').style.display = 'none';
        document.getElementById('computed-options').style.display = 'none';

        // Show relevant options
        if (fieldType === 'link') {
            document.getElementById('link-options').style.display = 'block';
        } else if (fieldType === 'select' || fieldType === 'multiselect') {
            document.getElementById('select-options').style.display = 'block';
        } else if (fieldType === 'table') {
            document.getElementById('table-options').style.display = 'block';
        } else if (fieldType === 'computed') {
            document.getElementById('computed-options').style.display = 'block';
        }
    }

    function saveField() {
        // Validate required fields manually
        const fieldName = document.getElementById('field-name').value.trim();
        const fieldLabel = document.getElementById('field-label').value.trim();
        const fieldType = document.getElementById('field-type').value;

        if (!fieldName) {
            alert('Field Name is required');
            document.getElementById('field-name').focus();
            return;
        }

        if (!fieldLabel) {
            alert('Field Label is required');
            document.getElementById('field-label').focus();
            return;
        }

        // Validate field name pattern (lowercase letters and underscores only)
        if (!/^[a-z_]+$/.test(fieldName)) {
            alert('Field Name must contain only lowercase letters and underscores');
            document.getElementById('field-name').focus();
            return;
        }

        // Collect field data
        const fieldData = {
            name: document.getElementById('field-name').value.trim(),
            label: document.getElementById('field-label').value.trim(),
            type: document.getElementById('field-type').value,
            default: document.getElementById('field-default').value.trim(),
            required: document.getElementById('field-required').checked,
            unique: document.getElementById('field-unique').checked,
            readonly: document.getElementById('field-readonly').checked,
            description: document.getElementById('field-description').value.trim(),
        };

        // Add type-specific data
        if (fieldData.type === 'link') {
            const linkDoctype = document.getElementById('link-doctype').value.trim();
            if (!linkDoctype) {
                alert('Please select a Link Doctype');
                return;
            }
            fieldData.link_doctype = linkDoctype;
        } else if (fieldData.type === 'select' || fieldData.type === 'multiselect') {
            const optionsStr = document.getElementById('select-options-input').value.trim();
            if (!optionsStr) {
                alert('Please enter options for the select field');
                return;
            }
            fieldData.options = optionsStr.split(',').map(o => o.trim()).filter(o => o);
        } else if (fieldData.type === 'table') {
            const childDoctype = document.getElementById('child-doctype').value.trim();
            if (!childDoctype) {
                alert('Please select a Child Doctype. Make sure you have created a child doctype first (with is_child checked).');
                return;
            }
            fieldData.child_doctype = childDoctype;
        } else if (fieldData.type === 'computed') {
            const formula = document.getElementById('formula').value.trim();
            if (!formula) {
                alert('Please enter a formula for the computed field');
                return;
            }
            fieldData.formula = formula;
        }

        // Clean up empty strings
        Object.keys(fieldData).forEach(key => {
            if (fieldData[key] === '') {
                delete fieldData[key];
            }
        });

        // Add or update field
        if (editingFieldIndex !== null) {
            fields[editingFieldIndex] = fieldData;
        } else {
            fields.push(fieldData);
        }

        // Re-render and update schema
        renderFields();
        updateSchemaField();

        // Close modal
        closeFieldModal();
    }

    function editField(index) {
        if (index >= 0 && index < fields.length) {
            openFieldModal(fields[index], index);
        }
    }

    function deleteField(index) {
        if (confirm('Are you sure you want to delete this field?')) {
            fields.splice(index, 1);
            renderFields();
            updateSchemaField();
        }
    }

    function updateSchemaField() {
        // Find the hidden schema textarea
        const schemaField = document.getElementById('id_schema');
        if (!schemaField) return;

        // Get existing schema or create new
        let schema = {};
        try {
            const currentValue = schemaField.value.trim();
            if (currentValue) {
                schema = JSON.parse(currentValue);
            }
        } catch (e) {
            console.warn('Could not parse existing schema, creating new one');
        }

        // Update fields in schema
        schema.fields = fields;

        // Write back to textarea
        schemaField.value = JSON.stringify(schema, null, 2);
    }

    function importJSON() {
        const jsonStr = prompt('Paste your JSON schema here:');
        if (!jsonStr) return;

        try {
            const data = JSON.parse(jsonStr);

            // Check if it's a full schema or just fields array
            if (Array.isArray(data)) {
                fields = data;
            } else if (data.fields && Array.isArray(data.fields)) {
                fields = data.fields;
            } else {
                alert('Invalid JSON format. Expected array of fields or schema object with "fields" property.');
                return;
            }

            renderFields();
            updateSchemaField();
            alert('JSON imported successfully!');
        } catch (e) {
            alert('Invalid JSON: ' + e.message);
        }
    }

    function exportJSON() {
        const schema = {
            fields: fields
        };

        const jsonStr = JSON.stringify(schema, null, 2);

        // Create temporary textarea to copy to clipboard
        const textarea = document.createElement('textarea');
        textarea.value = jsonStr;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();

        try {
            document.execCommand('copy');
            alert('Schema copied to clipboard!');
        } catch (e) {
            // Fallback: show in alert
            prompt('Copy this JSON:', jsonStr);
        }

        document.body.removeChild(textarea);
    }

})();
