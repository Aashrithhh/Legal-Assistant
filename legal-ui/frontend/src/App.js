import React, { useState, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";

const API_BASE = "http://127.0.0.1:8000";

function riskBadgeColor(risk) {
  const r = (risk || "").toLowerCase();
  if (r === "high") return "bg-red-100 text-red-700 border-red-300";
  if (r === "medium") return "bg-yellow-100 text-yellow-700 border-yellow-300";
  if (r === "low") return "bg-green-100 text-green-700 border-green-300";
  return "bg-gray-100 text-gray-700 border-gray-300";
}

export default function App() {
  const [activeTab, setActiveTab] = useState("analysis");
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [currentCaseId, setCurrentCaseId] = useState(null);

  const [formData, setFormData] = useState({
    matterOverview: "",
    peopleAndAliases: "",
    noteworthyOrganizations: "",
    noteworthyTerms: "",
    additionalContext: "",
  });

  const [result, setResult] = useState(null);

  const handleInputChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const addFiles = (files) => {
    const maxSize = 100 * 1024 * 1024;
    const arr = Array.from(files);
    const valid = arr.filter((file) => {
      if (file.size > maxSize) {
        alert(`File "${file.name}" exceeds 100MB.`);
        return false;
      }
      return true;
    });
    setUploadedFiles((prev) => [...prev, ...valid]);
  };

  const handleFileInputChange = (e) => {
    if (e.target.files) addFiles(e.target.files);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const removeFile = (index) => {
    setUploadedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  // 🔁 UPDATED FUNCTION
  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg(null);

    if (uploadedFiles.length === 0) {
      setErrorMsg("Please upload at least one document.");
      return;
    }
    if (!formData.matterOverview.trim()) {
      setErrorMsg("Matter Overview is required.");
      return;
    }

    // Build FormData the way FastAPI expects it
    const fd = new FormData();

    // 1) All uploaded files under key "files"
    uploadedFiles.forEach((file) => {
      fd.append("files", file);
    });

    // 2) All your text fields packed into one JSON string under key "metadata"
    fd.append("metadata", JSON.stringify(formData));

    try {
      setIsLoading(true);
      setResult(null);

      const res = await fetch(`${API_BASE}/api/analyze-case`, {
        method: "POST",
        body: fd, // no manual Content-Type header!
      });

      if (!res.ok) {
        const text = await res.text();
        console.error("Backend error:", res.status, text);
        setErrorMsg(`Error analyzing case (status ${res.status}).`);
        return;
      }

      const data = await res.json();
      setResult(data);
      setActiveTab("analysis");

      if (data.caseId) {
        setCurrentCaseId(data.caseId);
      }
    } catch (e) {
      console.error(e);
      setErrorMsg("Error analyzing case.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", height: "100vh", background: "#f8f9fa" }}>
      {/* LEFT PANEL */}
      <div
        style={{
          flex: "0 0 40%",
          background: "#fff",
          borderRight: "1px solid #ddd",
          overflowY: "auto",
          padding: "20px",
        }}
      >
        <h2 style={{ marginBottom: "10px" }}>Case Summary</h2>

        {/* Upload */}
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          style={{
            border: "2px dashed #bbb",
            padding: "20px",
            textAlign: "center",
            background: isDragging ? "#e0f0ff" : "#f7f7f7",
            cursor: "pointer",
            marginBottom: "15px",
          }}
        >
          <input
            type="file"
            multiple
            className="hidden"
            id="file-upload"
            onChange={handleFileInputChange}
          />
          <label htmlFor="file-upload" style={{ color: "#007bff" }}>
            Click to choose files
          </label>
          <span style={{ marginLeft: 5, color: "#666" }}>or drag & drop</span>
        </div>

        {uploadedFiles.length > 0 &&
          uploadedFiles.map((file, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "5px",
                background: "#eef3ff",
                marginBottom: "5px",
                borderRadius: 4,
              }}
            >
              <span>{file.name}</span>
              <button
                style={{ border: "none", background: "transparent", color: "red" }}
                onClick={() => removeFile(i)}
              >
                ✕
              </button>
            </div>
          ))}

        <textarea
          placeholder="Matter Overview *"
          value={formData.matterOverview}
          onChange={(e) => handleInputChange("matterOverview", e.target.value)}
          style={{
            width: "100%",
            height: 140,
            padding: 10,
            marginTop: 20,
            border: "1px solid #ccc",
          }}
        />

        <textarea
          placeholder="People & Aliases"
          value={formData.peopleAndAliases}
          onChange={(e) =>
            handleInputChange("peopleAndAliases", e.target.value)
          }
          style={{
            width: "100%",
            height: 80,
            padding: 10,
            marginTop: 20,
            border: "1px solid #ccc",
          }}
        />

        <textarea
          placeholder="Organizations"
          value={formData.noteworthyOrganizations}
          onChange={(e) =>
            handleInputChange("noteworthyOrganizations", e.target.value)
          }
          style={{
            width: "100%",
            height: 80,
            padding: 10,
            marginTop: 20,
            border: "1px solid #ccc",
          }}
        />

        <textarea
          placeholder="Noteworthy Terms"
          value={formData.noteworthyTerms}
          onChange={(e) =>
            handleInputChange("noteworthyTerms", e.target.value)
          }
          style={{
            width: "100%",
            height: 80,
            padding: 10,
            marginTop: 20,
            border: "1px solid #ccc",
          }}
        />
        <textarea
          placeholder="Additional Context (optional)"
          value={formData.additionalContext}
          onChange={(e) =>
            handleInputChange("additionalContext", e.target.value)
          }
          style={{
            width: "100%",
            height: 80,
            padding: 10,
            marginTop: 20,
            border: "1px solid #ccc",
          }}
        />

        <button
          onClick={handleSubmit}
          disabled={isLoading}
          style={{
            marginTop: 20,
            width: "100%",
            padding: 12,
            background: "#007bff",
            color: "#fff",
            border: "none",
            borderRadius: 5,
          }}
        >
          {isLoading ? "Analyzing..." : "Generate Response"}
        </button>

        {errorMsg && (
          <div style={{ marginTop: 10, color: "red", fontSize: 13 }}>
            {errorMsg}
          </div>
        )}
      </div>

      {/* RIGHT PANEL */}
      <div style={{ flex: 1, overflowY: "auto", padding: 20 }}>
        <h2>AI Response</h2>

        {!result && !isLoading && (
          <p style={{ color: "#777", fontStyle: "italic" }}>
            Fill the form and click Generate Response.
          </p>
        )}

        {isLoading && <p>Analyzing…</p>}

        {result && (
          <div style={{ marginTop: 10 }}>
            <h3>Summary</h3>
            <div style={{ background: "#fff", padding: 15, borderRadius: 6 }}>
              <ReactMarkdown>{result.analysis}</ReactMarkdown>
            </div>

            <h3 style={{ marginTop: 25 }}>Issues</h3>
            {result.issues && result.issues.length > 0 ? (
              result.issues.map((issue, idx) => (
                <div
                  key={idx}
                  style={{
                    background: "#fff",
                    padding: 12,
                    borderRadius: 6,
                    marginBottom: 10,
                    border: "1px solid #ddd",
                  }}
                >
                  <div
                    style={{ display: "flex", justifyContent: "space-between" }}
                  >
                    <strong>{issue.title}</strong>
                    <span
                      style={{
                        padding: "2px 6px",
                        borderRadius: 4,
                        border: "1px solid #ccc",
                        fontSize: 12,
                      }}
                      className={riskBadgeColor(issue.riskLevel)}
                    >
                      {issue.riskLevel}
                    </span>
                  </div>
                  <p style={{ fontSize: 13 }}>{issue.description}</p>
                  {issue.citations && (
                    <p style={{ fontSize: 11, color: "#444" }}>
                      <strong>Citations:</strong> {issue.citations}
                    </p>
                  )}
                </div>
              ))
            ) : (
              <p style={{ color: "#777" }}>No issues found.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
