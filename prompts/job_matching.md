Evaluate how well the following job matches the candidate profile.

## Job Details
Company: $company
Role: $title
Location: $location
Employment Type: $employment_type
Description:
$description

## Candidate Profile
Name: $name
Title: $profile_title
Skills: $skills
Experience: $experience
Education: $education

## Output Format
Return a JSON object with these fields:
- match_score: integer 0-100
- strengths: list of strings (top reasons this candidate fits)
- missing_skills: list of strings (important qualifications the candidate lacks)
- summary: string (1-2 sentence overall assessment)
