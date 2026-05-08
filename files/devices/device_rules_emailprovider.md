[Device Summary]
<Device "EmailProvider">
  <Service "SendMail" type="action">Send an email (to, subject, body)</Service>
  <Service "SendMailWithFile" type="action">Send an email with a file attachment</Service>
</Device>

# EmailProvider Examples

[Command]
Send an email to John saying I'm late
["EmailProvider.SendMail"]

[Command]
Email the report file to the team
["EmailProvider.SendMailWithFile"]

[Command]
Send a notification email
["EmailProvider.SendMail"]
