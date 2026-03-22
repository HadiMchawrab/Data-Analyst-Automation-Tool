import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import './TopicDetailsPage.css';

const TopicDetailsPage = () => {
  const location = useLocation();
  const navigate = useNavigate();
  
  const topic = location.state?.topic;
  const allTables = location.state?.tables || [];
  
  // Get tables from GPT_Columns for current topic
  const getGptTablesAndColumns = () => {
    const gptData = topic?.GPT_Columns?.[0]?.[0] || {};
    return gptData;
  };
  
  // Check if a table has any columns not used by GPT
  const hasAvailableColumns = (tableName) => {
    const gptData = getGptTablesAndColumns();
    const gptColumns = gptData[tableName] || [];
    
    // Get all columns for this table
    const tableObj = allTables.find(obj => Object.keys(obj)[0] === tableName);
    const allColumns = tableObj ? tableObj[tableName] : [];
    
    // Return true if there are any columns not in GPT's selection
    return allColumns.some(column => !gptColumns.includes(column));
  };
  
  // Get all available tables that have unused columns
  const getAvailableTablesFromAll = () => {
    // Get all available tables from the initial data
    const availableTables = allTables.map(tableObj => Object.keys(tableObj)[0]);
    return availableTables.filter(table => hasAvailableColumns(table));
  };

  // Get available columns that aren't in GPT_Columns for the selected table
  const getAvailableColumnsForTable = (tableName) => {
    const gptData = getGptTablesAndColumns();
    const gptColumns = gptData[tableName] || [];
    const tableObj = allTables.find(obj => Object.keys(obj)[0] === tableName);
    const allColumns = tableObj ? tableObj[tableName] : [];
    return allColumns.filter(column => !gptColumns.includes(column));
  };
  
  const [dropdownRows, setDropdownRows] = useState([
    { id: 1, selectedTable: '', selectedColumns: [] }
  ]);

  const handleAddRow = () => {
    const newRow = {
      id: Date.now(),
      selectedTable: '',
      selectedColumns: []
    };
    setDropdownRows([...dropdownRows, newRow]);
  };

  const handleRemoveRow = (rowId) => {
    setDropdownRows(dropdownRows.filter(row => row.id !== rowId));
  };

  const handleTableChange = (rowId, table) => {
    setDropdownRows(dropdownRows.map(row => {
      if (row.id === rowId) {
        return { ...row, selectedTable: table, selectedColumns: [] };
      }
      return row;
    }));
  };

  const handleColumnChange = (rowId, selectedOptions) => {
    setDropdownRows(dropdownRows.map(row => {
      if (row.id === rowId) {
        return { ...row, selectedColumns: selectedOptions };
      }
      return row;
    }));
  };

  const getAvailableTables = (currentRowId) => {
    const availableTables = getAvailableTablesFromAll();
    const selectedTables = dropdownRows
      .filter(row => row.id !== currentRowId)
      .map(row => row.selectedTable);
    return availableTables.filter(table => !selectedTables.includes(table));
  };

  const handleContinue = async () => {
    // Get ALL GPT-selected columns from all tables (not just the first one)
    const allGptData = {};
    if (topic?.GPT_Columns && Array.isArray(topic.GPT_Columns)) {
      topic.GPT_Columns.forEach(gptSet => {
        if (!Array.isArray(gptSet)) return;
        gptSet.forEach(tableObj => {
          if (!tableObj || typeof tableObj !== 'object') return;
          Object.entries(tableObj).forEach(([tableName, columns]) => {
            if (!Array.isArray(columns)) return;
            if (!allGptData[tableName]) {
              allGptData[tableName] = new Set(columns);
            } else {
              columns.forEach(col => allGptData[tableName].add(col));
            }
          });
        });
      });
    }

    // Convert Sets to Arrays
    const mergedTables = {};
    Object.entries(allGptData).forEach(([tableName, columnsSet]) => {
      mergedTables[tableName] = Array.from(columnsSet);
    });
    
    // Then merge user-selected columns
    // Ensure all GPT tables are initialized even if user selects no columns
dropdownRows.forEach(row => {
  if (row.selectedTable && !mergedTables[row.selectedTable]) {
    mergedTables[row.selectedTable] = []; // Initialize table if user selects it but no columns
  }
});

    dropdownRows.forEach(row => {
      if (row.selectedTable && row.selectedColumns.length > 0) {
        if (mergedTables[row.selectedTable]) {
          // Add to existing table's columns, avoiding duplicates
          const existingColumns = new Set(mergedTables[row.selectedTable]);
          row.selectedColumns.forEach(col => existingColumns.add(col));
          mergedTables[row.selectedTable] = Array.from(existingColumns);
        } else {
          // Create new table entry
          mergedTables[row.selectedTable] = [...row.selectedColumns];
        }
      }
    });

    // Data for backend
    const submissionData = {
      topic: topic.topic,
      Relationship: Array.from(topic.Relationship || []),
      ML_Models: Array.from(topic.ML_Models || []),
      tables: mergedTables
    };

    // Navigate to analysis with all the data
    navigate('/analysis', { 
      state: { 
        topic: topic,
        tables: mergedTables,
        submissionData: submissionData
      }
    });
  };

  if (!topic) {
    return <div className="topic-details-page">No topic selected</div>;
  }

  const availableTables = getAvailableTablesFromAll();

  return (
    <div className="topic-details-page">
      <h2>{topic.topic}</h2>
      
      <div className="topic-info">
        <div className="topic-info-section">
          <span className="topic-label">Reasoning:</span>
          <span className="topic-content">
            {topic.reasoning}
          </span>
        </div>

        <div className="topic-info-section">
          <span className="topic-label">Needs:</span>
          <span className="topic-content">
            {topic.Needs}
          </span>
        </div>

        <div className="topic-info-section">
          <span className="topic-label">Relationship:</span>
          <span className="topic-content">
            {topic.Relationship && Array.from(topic.Relationship).join('. ')}
          </span>
        </div>

        <div className="topic-info-section">
          <span className="topic-label">ML Models:</span>
          <span className="topic-content">
            {topic.ML_Models && Array.from(topic.ML_Models).join(', ')}
          </span>
        </div>

        <div className="topic-info-section">
          <span className="topic-label">GPT Selected Columns:</span>
          <span className="topic-content">
            {topic.GPT_Columns && Array.isArray(topic.GPT_Columns) &&
              topic.GPT_Columns.flat().map((tableObj, index) => {
                if (!tableObj || typeof tableObj !== 'object') return null;
                const entries = Object.entries(tableObj);
                if (entries.length === 0) return null;
                const [tableName, columns] = entries[0];
                return (
                  <div key={index}>
                    <em>{tableName}:</em> {Array.isArray(columns) ? columns.join(", ") : String(columns)}
                  </div>
                );
              })}
          </span>
        </div>




        </div>

      <h3 className="selection-title">Choose Additional Tables and Columns for Analysis</h3>
      <div className="selection-container">
        {dropdownRows.map((row, index) => (
          <div key={row.id} className="selection-row">
            {index === dropdownRows.length - 1 && (
              <button 
                className="add-row-button"
                onClick={handleAddRow}
                disabled={dropdownRows.length >= availableTables.length}
              >
                +
              </button>
            )}
            {dropdownRows.length > 1 && (
              <button 
                className="remove-row-button"
                onClick={() => handleRemoveRow(row.id)}
              >
                −
              </button>
            )}
            <div className="selection-section">
              <div className="dropdown-group">
                <label htmlFor={`table-select-${row.id}`}>Select Additional Table:</label>
                <select 
                  id={`table-select-${row.id}`}
                  value={row.selectedTable}
                  onChange={(e) => handleTableChange(row.id, e.target.value)}
                >
                  <option value="">-- Select a table --</option>
                  {getAvailableTables(row.id).map((table, index) => (
                    <option key={index} value={table}>{table}</option>
                  ))}
                </select>
              </div>

              <div className="dropdown-group">
                <label htmlFor={`column-select-${row.id}`}>Select Additional Columns:</label>
                <select 
                  id={`column-select-${row.id}`}
                  multiple 
                  value={row.selectedColumns}
                  onChange={(e) => {
                    const options = Array.from(e.target.selectedOptions, option => option.value);
                    handleColumnChange(row.id, options);
                  }}
                  disabled={!row.selectedTable}
                >
                  {row.selectedTable && getAvailableColumnsForTable(row.selectedTable).map((column, index) => (
                    <option key={index} value={column}>{column}</option>
                  ))}
                </select>
                <p className="column-hint">Hold Ctrl (Windows) or ⌘ (Mac) to select multiple columns</p>
                {row.selectedColumns.length > 0 && (
                  <div className="selected-columns-info">
                    {row.selectedColumns.length} column{row.selectedColumns.length !== 1 ? 's' : ''} selected
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="continue-section">
        <button 
          className="continue-button"
          onClick={handleContinue}
        >
          Continue to Analysis
        </button>
      </div>
    </div>
  );
};

export default TopicDetailsPage;