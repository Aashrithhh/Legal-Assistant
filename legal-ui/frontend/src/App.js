import React, { useState, useEffect, useCallback } from "react";
import ReactMarkdown from 'react-markdown';

// Updated: 2025-12-17 - Backend on port 8001
const API_BASE = "http://127.0.0.1:8001";

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
  const [rightInput, setRightInput] = useState("");
  const [rightResponse, setRightResponse] = useState("");

  // Q&A History state (frontend-only, lost on page refresh)
  const [askQuestion, setAskQuestion] = useState("");
  const [isAskLoading, setIsAskLoading] = useState(false);
  const [qaHistory, setQaHistory] = useState([]);

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
      console.log("=== API RESPONSE ===", data);
      console.log("Sources:", data.sources);
      console.log("Issues count:", data.issues?.length);
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

  const handleAskQuestion = async () => {
    const trimmedQuestion = askQuestion.trim();
    if (!trimmedQuestion) return;

    try {
      setIsAskLoading(true);

      // Reuse existing ask logic
      const payload = {
        question: trimmedQuestion,
        history: qaHistory.map((item) => ({
          role: "user",
          content: item.question,
        })),
      };

      const res = await fetch(`${API_BASE}/api/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        console.error("Ask endpoint error:", res.status);
        return;
      }

      const data = await res.json();
      const answerText = data.answer || "";

      // Add to Q&A history
      setQaHistory((prev) => [
        ...prev,
        {
          id: prev.length + 1,
          question: trimmedQuestion,
          answer: answerText,
          time: new Date().toLocaleString(),
        },
      ]);

      setAskQuestion("");
    } catch (e) {
      console.error("Error asking question:", e);
    } finally {
      setIsAskLoading(false);
    }
  };

  const handleClearAskSession = () => {
    setAskQuestion("");
    setQaHistory([]);
    setIsAskLoading(false);
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

        {/* New: Right-panel interactive input targeted to Claude Haiku */}
        <div style={{ marginBottom: 12 }}>
          <textarea
            placeholder="Type instructions for Claude Haiku here..."
            value={rightInput}
            onChange={(e) => setRightInput(e.target.value)}
            style={{ width: "100%", height: 100, padding: 10, border: "1px solid #ccc" }}
          />
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button
              onClick={async () => {
                if (!rightInput.trim()) return;
                try {
                  setIsLoading(true);
                  setRightResponse("");
                  const fd = new FormData();
                  // Use anthro pic provider
                  fd.append("provider", "anthropic");
                  fd.append("prompt", rightInput);

                  const res = await fetch(`${API_BASE}/api/chat`, {
                    method: "POST",
                    body: fd,
                  });
                  if (!res.ok) {
                    const txt = await res.text();
                    setRightResponse(`Error: ${res.status} ${txt}`);
                  } else {
                    const j = await res.json();
                    setRightResponse(j.text || "");
                  }
                } catch (e) {
                  setRightResponse("Error calling server.");
                } finally {
                  setIsLoading(false);
                }
              }}
              style={{ padding: "8px 14px", background: "#0ea5e9", color: "white", border: "none", borderRadius: 4 }}
            >
              Send to Claude Haiku
            </button>
          </div>
        </div>

        {rightResponse && (
          <div style={{ marginBottom: 18 }}>
            <h4>Claude Haiku Response</h4>
            <div style={{ background: "#fff", padding: 12, borderRadius: 6 }}>
              <ReactMarkdown>{rightResponse}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* Q&A History Section */}
        <div
          style={{
            marginTop: 30,
            marginBottom: 20,
            background: "#fff",
            borderRadius: 12,
            overflow: "hidden",
            boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
          }}
        >
          {/* Q&A Header */}
          <div
            style={{
              background: "#1e3a8a",
              color: "white",
              padding: "12px 16px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <h3 style={{ margin: 0, fontSize: 16 }}>Ask a Question</h3>
            <button
              onClick={handleClearAskSession}
              style={{
                border: "none",
                background: "rgba(255,255,255,0.1)",
                color: "#e5e7eb",
                borderRadius: 999,
                padding: "4px 10px",
                fontSize: 12,
                cursor: "pointer",
              }}
            >
              Clear session
            </button>
          </div>

          {/* Input Section */}
          <div style={{ padding: 16 }}>
            <textarea
              placeholder="Type your question here..."
              value={askQuestion}
              onChange={(e) => setAskQuestion(e.target.value)}
              style={{
                width: "100%",
                height: 80,
                padding: 10,
                border: "1px solid #ccc",
                borderRadius: 6,
                fontFamily: "inherit",
                fontSize: 14,
                resize: "vertical",
              }}
            />
            <button
              onClick={handleAskQuestion}
              disabled={isAskLoading}
              style={{
                marginTop: 10,
                width: "100%",
                padding: 10,
                background: isAskLoading ? "#999" : "#0ea5e9",
                color: "white",
                border: "none",
                borderRadius: 6,
                cursor: isAskLoading ? "not-allowed" : "pointer",
                fontSize: 14,
                fontWeight: 500,
              }}
            >
              {isAskLoading ? "Thinking…" : "Ask"}
            </button>
          </div>

          {/* Q&A History */}
          <div style={{ borderTop: "1px solid #e5e7eb", maxHeight: 400, overflowY: "auto" }}>
            {qaHistory.length === 0 ? (
              <p style={{ padding: 16, color: "#999", fontStyle: "italic", margin: 0 }}>
                No questions asked yet in this session.
              </p>
            ) : (
              <div>
                {[...qaHistory].reverse().map((item) => (
                  <div
                    key={item.id}
                    style={{
                      padding: 12,
                      borderBottom: "1px solid #f0f0f0",
                      background: item.id % 2 === 0 ? "#f9f9f9" : "#fff",
                    }}
                  >
                    <p style={{ margin: "0 0 4px 0", fontSize: 11, color: "#666" }}>
                      {item.time}
                    </p>
                    <p style={{ margin: "4px 0", fontSize: 13, fontWeight: 600 }}>
                      Q: {item.question}
                    </p>
                    <p style={{ margin: "4px 0 0 0", fontSize: 13, lineHeight: 1.5 }}>
                      A: {item.answer}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Claude Haiku Input (above result section) */}
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
                    <p style={{ fontSize: 11, color: "#444", marginTop: 6 }}>
                      <strong>Citations:</strong> {issue.citations}
                    </p>
                  )}
                </div>
              ))
            ) : (
              <p style={{ color: "#777" }}>No issues found.</p>
            )}

            {result.sources && result.sources.length > 0 && (
              <div style={{ marginTop: 18 }}>
                <h4 style={{ marginBottom: 6 }}>Sources used</h4>
                <ul style={{ paddingLeft: 16, margin: 0 }}>
                  {result.sources.map((src, i) => (
                    <li key={i} style={{ fontSize: 12, color: "#334155" }}>
                      {src.file} (score {src.score.toFixed(4)})
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
