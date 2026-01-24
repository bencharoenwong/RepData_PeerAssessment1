# Skill: search_academics_policymakers

## Purpose
Extract program/scientific committee members from academic conferences, research their backgrounds, and compile contact information for targeted outreach based on paper alignment.

## When to Use
- User provides a conference URL and wants to identify relevant contacts
- User has a paper/research and wants to find aligned academics for sharing
- User needs to build an outreach list from a committee/speaker roster

## Input Required
1. **Conference URL** - Link to the conference page with committee/speaker information
2. **Paper Summary** (optional) - Brief description of user's research to score relevance
3. **Target Section** - Which committee to extract (e.g., "program committee", "scientific committee", "organizing committee", "speakers")

## Workflow

### Step 1: Extract Committee Members
```
Use WebFetch on the conference URL with prompt:
"Find the [target section] members listed on this page. Extract all names and affiliation information."
```

### Step 2: Research Each Member (Parallel Searches)
For each committee member, use WebSearch:
```
Query: "[Name] [Affiliation] research [relevant keywords]"
```

Focus on finding:
- Current position and institution
- Primary research areas
- Recent notable publications
- Email address (often in search results or faculty pages)

### Step 3: Find Email Addresses
If email not found in initial search:
```
WebFetch on faculty profile URL with prompt: "Find the email address for [Name]"
```

Or search:
```
Query: "[Name] [Institution] email contact"
```

### Step 4: Score Relevance (if paper provided)
Rate each person 1-10 based on:
- **10**: Direct overlap with paper topic (same domain + methodology)
- **8-9**: Strong thematic alignment (same domain, different angle)
- **6-7**: Related field with transferable insights
- **4-5**: General AI/tech governance relevance
- **1-3**: Tangential connection only

### Step 5: Compile Output
Generate CSV with columns:
- Name
- Affiliation
- Email
- Research Focus
- Relevance Score
- Priority Tier (Tier 1-4)
- Key Relevance Notes

## Output Format

### CSV Structure
```csv
Name,Affiliation,Email,Research Focus,Relevance Score,Priority Tier,Key Relevance Notes
[Name],[Institution],[email@domain.edu],"[2-3 key research areas]",[1-10],[Tier 1-4],"[Specific connection to user's paper]"
```

### Priority Tiers
- **Tier 1** (Score 9-10): Strongest alignment, prioritize outreach
- **Tier 2** (Score 7-8): Strong alignment, high-value contacts
- **Tier 3** (Score 5-6): Moderate alignment, worth reaching out
- **Tier 4** (Score 1-4): Lower priority, situational outreach

## Example Invocation

User prompt:
```
[Conference URL]

Research my paper alignment with the program committee. My paper summary:
[Paper abstract/summary]

Focus on: [scientific committee / program committee / speakers]
Output: CSV for Google Sheets
```

## Tips for Efficiency
1. **Batch WebSearch calls** - Search 3-5 people in parallel
2. **Use institution email patterns** - Most academics follow [username]@[institution].edu
3. **Check Google Scholar** - Often has verified email domains
4. **Faculty pages** - Primary source for email and research focus
5. **Skip deep dives on low-relevance** - Quick scan for Tier 4 candidates

## Common Conference Committee Types
- Program Committee / Scientific Committee (paper reviewers)
- Organizing Committee (logistics, less relevant for paper sharing)
- Keynote Speakers / Invited Speakers (high visibility, often senior)
- Advisory Board (strategic oversight, senior academics)
- Session Chairs (topic-specific expertise)

## Email Address Patterns by Institution Type
- US Universities: firstname.lastname@university.edu or initials@university.edu
- Law Schools: lastname@law.university.edu
- Business Schools: lastname@school.university.edu
- European: varies widely, check faculty page
- Asian: often uses employee ID numbers
