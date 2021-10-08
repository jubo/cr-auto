from __future__ import print_function

import shutil
import os.path
import datetime
import os
import urllib.request, json 

import locale
locale.setlocale(locale.LC_TIME,'')

PRIVATE_KEY_GITLAB_API = os.environ['PRIVATE_KEY_GITLAB_API']
URL_PROJECTS_GITLAB = "https://git.miist.fr/api/v4/projects?private_token=%s" % PRIVATE_KEY_GITLAB_API
URL_ACTIVITY_GITLAB = "https://git.miist.fr/api/v4/events?private_token=%s" % PRIVATE_KEY_GITLAB_API
WHOIS = "JBOUCHER"

class Activity:
  """
  Classe activité dans gitlab
  """
  project_name=""
  name = ""
  items = []

  def __str__(self):
    return """<p><span class="activity">[%s]</span><ul>%s</ul></p><div class="timeleft">Temps passé : xx</div>""" % ( self.name,  "\n".join(map(Activity.item_to_html, self.items)))

  def item_to_html(item):
    return "<li>%s</li>" % item
  

def get_project_from_gitlab(start):
  projects = {}

  strurl = URL_PROJECTS_GITLAB+"&last_activity_after=="+start
  with urllib.request.urlopen(strurl) as url:
    print("request projects to %s" % strurl)
    data = json.loads(url.read().decode())
    #print("json result =" )
    for p in data:
      projects[p['id']] = p['name']
    
    #print(projects)
  
  return projects

def get_activity_from_name(name, arr):
  for a in arr:
    if a.name == name:
      return a
  return None

def get_activity_from_gitlab(projects, start, end):
  activities = []
  strurl = URL_ACTIVITY_GITLAB+"&after="+start
  with urllib.request.urlopen(strurl) as url:
    print("request activity to %s" % strurl)
    data = json.loads(url.read().decode())
    for item in data:
      if item["action_name"] == "pushed to" or item["action_name"] == "pushed new":
        pd = item["push_data"]
        project_name = projects[item['project_id']]
        name = pd["ref"].replace("feature/", "").upper()

        if(name != "DEV" and name != "MASTER"):
          a = get_activity_from_name(name, activities)
          mustappend = False
          if a is None:
            mustappend = True
            a = Activity()
            a.name = name
            
          commit_title = pd["commit_title"].capitalize()
          if("Merge remote-tracking branch" not in commit_title):
            item = "(%s) - %s" % (project_name, commit_title)
            a.items.append(item)

          if mustappend:
            a.items.sort()
            activities.append(a)
      else:
        print("action : " + item["action_name"])
        print("projet : " + projects[item['project_id']])
        print(item)

  
  return activities

def generate_report():
  """
  Genere un rapport html de l'activité git selon des conventions miist (branche feature/xxxx et commits.)
  """
  nbweek = datetime.datetime.now().strftime("%V")
  today = datetime.date.today()

  start_of_curweek = today + datetime.timedelta(days=-(today.weekday()))
  start_of_curweek_for_gitlab = today + datetime.timedelta(days=-(today.weekday()+1))
  end_of_curweek = today + datetime.timedelta(days=-(today.weekday()+1+2), weeks=1) 

  name = "%s - CR Hebdomadaire MIIST semaine %s" % (WHOIS, nbweek)
  
  original="cr-template.html"
  target="cr-miist-%s-%s.html" % (WHOIS, nbweek)
  shutil.copyfile(original, target)    

  # Read in the file
  with open(target, 'r') as file :
    filedata = file.read()

  # Replace the target string
  start_semaine = start_of_curweek.strftime('%d/%m/%Y')
  end_semaine = end_of_curweek.strftime('%d/%m/%Y')
  
  start = start_of_curweek_for_gitlab.strftime('%Y-%m-%d')
  end = end_of_curweek.strftime('%Y-%m-%d')

  filedata = filedata.replace('{{whois}}', WHOIS)
  filedata = filedata.replace('{{start_semaine}}', start_semaine)
  filedata = filedata.replace('{{end_semaine}}', end_semaine)
  filedata = filedata.replace('{{idx_semaine}}', nbweek)

  projects = get_project_from_gitlab(start)
  activities = get_activity_from_gitlab(projects, start, end)

  filedata = filedata.replace('{{activity}}', "\n".join(map(str, activities)))

  # Write the file out again
  with open(target, 'w') as file:
    file.write(filedata)    

  return (name, target)



def upload_to_gdrive(name, target):
  print("Nom fichier local : %s, target gdrive : %s" % (target, name))
  try:
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from apiclient.http import MediaFileUpload
    from apiclient import errors

    FOLDER_ID = '1gmOm_Z3YPnM03BjkER3IIyW86Rzda647'

    # If modifying these scopes, delete the file token.json.
    SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents']

    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    serviceDrive = build('drive', 'v3', credentials=creds)

    file_metadata = {
     'name': name,
     'mimeType': 'application/vnd.google-apps.docs',
     'parents': [FOLDER_ID]
    }
 
    media = MediaFileUpload(target,
                            mimetype='text/html',
                            resumable=True)

    f = serviceDrive.files().create(body=file_metadata,
                                    media_body=media,
                                    fields='id').execute()
    print('File ID: %s' % f.get('id'))
  except:
    print('Upload to GDrive impossible. A verifier !')

if __name__ == '__main__':
    name, target = generate_report()
    upload_to_gdrive(name, target)
