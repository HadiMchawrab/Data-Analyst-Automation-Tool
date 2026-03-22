import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import './DataAnalysisPage.css';

const DataAnalysisPage = () => {
    const location = useLocation();
    const navigate = useNavigate();
    const { analysisResult, tables, images_bytes, executed_training, training_retries } = location.state || {};

    const handleDownloadModel = () => {
        if (!executed_training?.model_weights) return;
        const bytes = atob(executed_training.model_weights);
        const arr = new Uint8Array(bytes.length);
        for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
        const blob = new Blob([arr], { type: 'application/octet-stream' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${executed_training.metrics?.model_name || 'model'}.pkl`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const handleRetry = () => {
        navigate(-1);
    };

    // Check for overall analysis result first
    if (!analysisResult) {
        return (
            <div className="data-analysis-page">
                <div className="error-container">
                    <h2>Error</h2>
                    <p>No analysis results available</p>
                    <button onClick={handleRetry} className="retry-button">
                        Retry Analysis
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="data-analysis-page">
            <h1>Data Analysis Results</h1>

            {/* Analysis Status */}
            <div className="analysis-status">
                <h2>Analysis Status</h2>
                <p>{analysisResult.message || "Analysis completed"}</p>
                {analysisResult.status && (
                    <p className={`status-badge ${analysisResult.status}`}>
                        Status: {analysisResult.status}
                    </p>
                )}
            </div>

            {/* Model Analysis Results */}
            {analysisResult.additionalData && (
                <div className="model-analysis">
                    <h2>Model Analysis</h2>
                    <div className="model-info">
                        <h3>Chosen Model</h3>
                        <p>{analysisResult.additionalData.chosen_models}</p>
                    </div>
                    <div className="model-info">
                        <h3>Model Analysis</h3>
                        <p>{analysisResult.additionalData.explained_models}</p>
                    </div>
                    <div className="model-info">
                        <h3>Training Script</h3>
                        <pre>{analysisResult.additionalData.final_scripts}</pre>
                    </div>
                </div>
            )}

            {/* Training Results */}
            {executed_training && (
                <div className="training-results">
                    <h2>Training Results</h2>
                    <div className="model-info">
                        <p className={`status-badge ${executed_training.status || ''}`}>
                            Status: {executed_training.status || 'unknown'}
                        </p>
                        {training_retries > 1 && (
                            <p className="retry-info">Model was retrained {training_retries} time{training_retries !== 1 ? 's' : ''} to improve performance</p>
                        )}
                    </div>

                    {executed_training.metrics && Object.keys(executed_training.metrics).length > 0 ? (
                        <div className="metrics-section">
                            {executed_training.metrics.model_name && (
                                <div className="model-info">
                                    <h3>Model</h3>
                                    <p>{executed_training.metrics.model_name}
                                       {executed_training.metrics.task_type && ` (${executed_training.metrics.task_type})`}
                                    </p>
                                </div>
                            )}
                            <div className="model-info">
                                <h3>Performance Metrics</h3>
                                <table className="metrics-table">
                                    <thead>
                                        <tr><th>Metric</th><th>Value</th></tr>
                                    </thead>
                                    <tbody>
                                        {Object.entries(executed_training.metrics)
                                            .filter(([key]) => !['model_name', 'task_type', 'classification_report'].includes(key))
                                            .map(([key, value]) => (
                                                <tr key={key}>
                                                    <td>{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</td>
                                                    <td>{typeof value === 'number' ? value.toFixed(4) : String(value)}</td>
                                                </tr>
                                            ))
                                        }
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    ) : (
                        <div className="model-info">
                            <p>Training completed but no metrics were captured. The model was saved successfully.</p>
                        </div>
                    )}

                    {executed_training.model_weights && (
                        <div className="model-info">
                            <button onClick={handleDownloadModel} className="download-model-button">
                                Download Trained Model (.pkl)
                            </button>
                        </div>
                    )}
                </div>
            )}

            {/* Selected Data Summary */}
            {tables && Object.keys(tables).length > 0 && (
                <div className="selected-data">
                    <h2>Analyzed Data</h2>
                    {Object.entries(tables).map(([tableName, columns], index) => (
                        <div key={index} className="data-item">
                            <h3>{tableName}</h3>
                            <p>Analyzed columns: {columns.join(', ')}</p>
                        </div>
                    ))}
                </div>
            )}

            {/* Visualization Results */}
            {images_bytes && Object.keys(images_bytes).length > 0 ? (
                Object.entries(images_bytes).map(([tableName, imageStrings]) => (
                    <div key={tableName} className="table-section">
                        <h2>{tableName} Visualizations</h2>
                        <div className="graphs-grid">
                            {imageStrings.map((base64String, index) => (
                                <div key={index} className="graph-container">
                                    <img 
                                        src={`data:image/png;base64,${base64String}`}
                                        alt={`${tableName} Analysis Graph ${index + 1}`}
                                        className="analysis-graph"
                                        onError={(e) => {
                                            e.target.style.display = 'none';
                                        }}
                                    />
                                </div>
                            ))}
                        </div>
                    </div>
                ))
            ) : (
                <div className="no-visualizations">
                    <p>No visualization graphs were generated during the analysis.</p>
                    <button onClick={handleRetry} className="retry-button">
                        Retry Analysis
                    </button>
                </div>
            )}
        </div>
    );
};

export default DataAnalysisPage;