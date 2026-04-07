[Device Summary]
<Device "EmailProvider">
  <Service "LatestEmail" type="value">Content of the most recent email</Service>
  <Service "UnreadCount" type="value">Number of unread emails</Service>
  <Service "SendEmail" type="action">Send an email (to, subject, body)</Service>
  <Service "CheckNewEmails" type="action">Fetch new emails from server</Service>
</Device>

# EmailProvider Examples

[Command]
Read the latest email from the EmailProvider
["EmailProvider.LatestEmail"]

[Command]
Send an email to John saying I'm late
["EmailProvider.SendEmail"]
