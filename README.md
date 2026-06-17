### Approach:
So we want to create an api layer that users can upload their .docx file, along with two compound names.

For data persistence I think the move would be to store everything as soon as possible. 

The flow would look like:
- User uploads file + compound names
- api takes the data and forwards it to a message queue - redis
- File has a UUID generated and is uploaded to a cloud storage bucket with that UUID as the name/key
- On successful upload, a row is added to a table, with the file's UUID saved, along with time/date uploaded
- once the row is added, the file is passed off to a task executer which processes the document, extracting/parsing the important data. This Parsed data is then inserted to the database, related to the original row with the UUID.
- finally another process picks up the parsed data and inserts it into the given sentences, inserts the return json, maybe through a JSONB column and then returns it to the user

This way we have stored the input and output of each step, leaving an audit trail all the way along.