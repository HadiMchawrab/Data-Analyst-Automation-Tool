import React from 'react';
import { Link } from 'react-router-dom';
import './HelpPage.css';

const HelpPage = () => {
  return (
    <div className="help-page">
      <h1>Help & Instructions</h1>
      
      <div className="help-content">
        <section className="help-section">
          <h2>Getting Started</h2>
          <p>
            Welcome to the AI Consultant application! This tool helps you analyze your data and suggests 
            machine learning models that could be beneficial for your business.
          </p>
        </section>

        <section className="help-section">
          <h2>Step 1: Upload Your Data</h2>
          <p>
            Start by uploading your CSV files. Each file should represent a table in your database.
            Make sure your files:
          </p>
          <ul>
            <li>Are in CSV format</li>
            <li>Have clear column headers</li>
            <li>Contain relevant business data</li>
          </ul>
        </section>

        <section className="help-section">
          <h2>Step 2: Review Topics</h2>
          <p>
            After processing your data, you'll see a list of suggested topics. Each topic includes:
          </p>
          <ul>
            <li>Relationships between your data</li>
            <li>Explanations of potential insights</li>
            <li>Suggested ML models based on your data</li>
            <li>Suggested ML models based on topic analysis</li>
          </ul>
        </section>

        <section className="help-section">
          <h2>Step 3: Select Tables and Columns</h2>
          <p>
            When you click on a topic, you can:
          </p>
          <ul>
            <li>Select multiple tables to add to the model analysis</li>
            <li>Choose specific columns from each table</li>
            <li>Add or remove table selections as needed</li>
            <li>See how many columns you've selected</li>
          </ul>
        </section>
        
        <section className="help-section">
          <h2>Tips</h2>
          <ul>
            <li>Hold Ctrl (Windows) or ⌘ (Mac) to select multiple columns</li>
            <li>You can add multiple table selections to analyze complex relationships, but make sure they are still relevant to the topic</li>
            <li>The green plus button adds new table selections</li>
            <li>The red minus button removes table selections (minimum one selection)</li>
          </ul>
        </section>
      </div>

      <div className="help-actions">
        <Link to="/" className="help-button">Back to Home</Link>
      </div>
    </div>
  );
};

export default HelpPage; 