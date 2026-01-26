/**
 * Google Apps Script for Conference Committee Monitor
 *
 * This runs entirely inside Google Sheets - no external hosting needed.
 *
 * SETUP:
 * 1. Open your Google Sheet
 * 2. Extensions → Apps Script
 * 3. Paste this code
 * 4. Add your Anthropic API key to Script Properties:
 *    - Click gear icon (Project Settings)
 *    - Scroll to "Script Properties"
 *    - Add: ANTHROPIC_API_KEY = your-key-here
 * 5. Run → processConferenceUrl() to test
 * 6. Optional: Set up a trigger for automation
 */

// Configuration
const CONFIG = {
  SHEET_NAME: "Conference Contacts",
  INPUT_SHEET: "URLs to Process",  // Sheet with conference URLs
  ANTHROPIC_MODEL: "claude-sonnet-4-20250514",
  PAPER_KEYWORDS: {
    high: ["financial advice", "consumer finance", "fintech regulation", "algorithmic fairness",
           "credit scoring", "consumer protection", "vulnerable investors", "AI discrimination"],
    medium: ["AI accountability", "algorithmic bias", "machine learning fairness", "AI regulation"],
    low: ["artificial intelligence", "technology law", "platform regulation"]
  }
};

/**
 * Custom menu for the spreadsheet
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('Conference Monitor')
    .addItem('Process URL in A1', 'processUrlFromCell')
    .addItem('Process All URLs', 'processAllUrls')
    .addSeparator()
    .addItem('Setup Sheets', 'setupSheets')
    .addToUi();
}

/**
 * Create required sheets if they don't exist
 */
function setupSheets() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // Create Contacts sheet
  let contactsSheet = ss.getSheetByName(CONFIG.SHEET_NAME);
  if (!contactsSheet) {
    contactsSheet = ss.insertSheet(CONFIG.SHEET_NAME);
    contactsSheet.appendRow([
      "Conference", "Date Added", "Name", "Affiliation", "Email",
      "Research Focus", "Relevant to Paper?", "Relevance Score",
      "Priority Tier", "Key Relevance Notes"
    ]);
    contactsSheet.getRange(1, 1, 1, 10).setFontWeight("bold");
  }

  // Create URL input sheet
  let urlSheet = ss.getSheetByName(CONFIG.INPUT_SHEET);
  if (!urlSheet) {
    urlSheet = ss.insertSheet(CONFIG.INPUT_SHEET);
    urlSheet.appendRow(["Conference Name", "URL", "Processed?"]);
    urlSheet.getRange(1, 1, 1, 3).setFontWeight("bold");
    urlSheet.appendRow(["Example Conference", "https://example.com/committee", "No"]);
  }

  SpreadsheetApp.getUi().alert('Sheets created! Add conference URLs to "' + CONFIG.INPUT_SHEET + '" sheet.');
}

/**
 * Process URL from cell A1 of active sheet
 */
function processUrlFromCell() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const url = sheet.getRange("A1").getValue();
  const name = sheet.getRange("B1").getValue() || "Unknown Conference";

  if (!url) {
    SpreadsheetApp.getUi().alert('Please enter a URL in cell A1');
    return;
  }

  processConference(url, name);
}

/**
 * Process all unprocessed URLs from the input sheet
 */
function processAllUrls() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const urlSheet = ss.getSheetByName(CONFIG.INPUT_SHEET);

  if (!urlSheet) {
    SpreadsheetApp.getUi().alert('Please run "Setup Sheets" first');
    return;
  }

  const data = urlSheet.getDataRange().getValues();

  for (let i = 1; i < data.length; i++) {
    const name = data[i][0];
    const url = data[i][1];
    const processed = data[i][2];

    if (url && processed !== "Yes") {
      try {
        processConference(url, name);
        urlSheet.getRange(i + 1, 3).setValue("Yes");
      } catch (e) {
        urlSheet.getRange(i + 1, 3).setValue("Error: " + e.message);
      }

      // Rate limiting
      Utilities.sleep(2000);
    }
  }
}

/**
 * Main function to process a conference
 */
function processConference(url, conferenceName) {
  Logger.log("Processing: " + conferenceName);

  // Fetch the webpage
  const response = UrlFetchApp.fetch(url);
  const html = response.getContentText();

  // Extract committee members using Claude
  const members = extractCommitteeMembers(html, url);
  Logger.log("Found " + members.length + " members");

  // Research each member and score relevance
  const results = [];
  for (const member of members) {
    const research = researchMember(member.name, member.affiliation);
    const scoring = scoreRelevance(research.research_focus, research.relevance_notes);

    results.push([
      conferenceName,
      new Date().toISOString().split('T')[0],
      member.name,
      member.affiliation,
      research.email,
      research.research_focus,
      scoring.relevance,
      scoring.score,
      scoring.tier,
      research.relevance_notes
    ]);

    // Rate limiting for API calls
    Utilities.sleep(1000);
  }

  // Append to contacts sheet
  if (results.length > 0) {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const contactsSheet = ss.getSheetByName(CONFIG.SHEET_NAME);
    contactsSheet.getRange(
      contactsSheet.getLastRow() + 1, 1,
      results.length, results[0].length
    ).setValues(results);
  }

  Logger.log("Added " + results.length + " contacts");
}

/**
 * Use Claude to extract committee members from HTML
 */
function extractCommitteeMembers(html, url) {
  const apiKey = PropertiesService.getScriptProperties().getProperty('ANTHROPIC_API_KEY');

  if (!apiKey) {
    throw new Error('ANTHROPIC_API_KEY not set in Script Properties');
  }

  // Clean HTML to text (basic)
  const text = html.replace(/<[^>]*>/g, '\n').substring(0, 15000);

  const prompt = `Extract all program committee, scientific committee, or organizing committee members from this webpage.

URL: ${url}

Page content:
${text}

Return a JSON array with objects containing:
- "name": full name
- "affiliation": institution/organization

Only include actual committee members. Return ONLY the JSON array.`;

  const response = callClaude(apiKey, prompt);

  try {
    const jsonMatch = response.match(/\[[\s\S]*\]/);
    if (jsonMatch) {
      return JSON.parse(jsonMatch[0]);
    }
  } catch (e) {
    Logger.log("Parse error: " + e);
  }

  return [];
}

/**
 * Research a committee member
 */
function researchMember(name, affiliation) {
  const apiKey = PropertiesService.getScriptProperties().getProperty('ANTHROPIC_API_KEY');

  const prompt = `Research this academic: ${name} at ${affiliation}

Provide JSON with:
{
  "email": "their@email.edu",
  "research_focus": "topic1, topic2, topic3",
  "relevance_notes": "Brief note on relevance to AI financial advice research"
}

Return ONLY JSON.`;

  try {
    const response = callClaude(apiKey, prompt);
    const jsonMatch = response.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      return JSON.parse(jsonMatch[0]);
    }
  } catch (e) {
    Logger.log("Research error for " + name + ": " + e);
  }

  return { email: "", research_focus: "", relevance_notes: "" };
}

/**
 * Score relevance based on keywords
 */
function scoreRelevance(researchFocus, relevanceNotes) {
  const text = (researchFocus + " " + relevanceNotes).toLowerCase();

  let highMatches = 0, medMatches = 0, lowMatches = 0;

  CONFIG.PAPER_KEYWORDS.high.forEach(kw => {
    if (text.includes(kw.toLowerCase())) highMatches++;
  });
  CONFIG.PAPER_KEYWORDS.medium.forEach(kw => {
    if (text.includes(kw.toLowerCase())) medMatches++;
  });
  CONFIG.PAPER_KEYWORDS.low.forEach(kw => {
    if (text.includes(kw.toLowerCase())) lowMatches++;
  });

  const score = Math.min(10, highMatches * 3 + medMatches * 2 + lowMatches);

  if (score >= 9) return { score, tier: "Tier 1", relevance: "Yes - Highly Relevant" };
  if (score >= 7) return { score, tier: "Tier 2", relevance: "Yes - Relevant" };
  if (score >= 5) return { score, tier: "Tier 3", relevance: "Somewhat Relevant" };
  return { score: Math.max(1, score), tier: "Tier 4", relevance: "Less Relevant" };
}

/**
 * Call Claude API
 */
function callClaude(apiKey, prompt) {
  const response = UrlFetchApp.fetch('https://api.anthropic.com/v1/messages', {
    method: 'post',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01'
    },
    payload: JSON.stringify({
      model: CONFIG.ANTHROPIC_MODEL,
      max_tokens: 4000,
      messages: [{ role: 'user', content: prompt }]
    })
  });

  const result = JSON.parse(response.getContentText());
  return result.content[0].text;
}
