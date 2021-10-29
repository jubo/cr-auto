from __future__ import print_function

# script de generation rapport hebdo HTML via extraciton historique des commits git

import shutil
import os.path
import datetime
import os
import urllib.request, json 

import locale
locale.setlocale(locale.LC_TIME,'')

PRIVATE_KEY_GITLAB_API = os.environ['PRIVATE_KEY_GITLAB_API']
URL_PROJECTS_GITLAB = "https://git.miist.fr/api/v4/projects?private_token=%s" % PRIVATE_KEY_GITLAB_API
URL_PROJECTS_GITLAB_BY_ID = "https://git.miist.fr/api/v4/projects/{{id}}?private_token=" + PRIVATE_KEY_GITLAB_API
URL_ACTIVITY_GITLAB = "https://git.miist.fr/api/v4/events?private_token=%s" % PRIVATE_KEY_GITLAB_API
WHOIS = "JBOUCHER"

class Activity:
  """
  Classe activité dans gitlab
  """
  def __init__(self):
    self.project_name=""
    self.name = ""
    self.items = []

  def __str__(self):
    return """<p><span class="activity">[%s]</span><ul>%s</ul></p><div class="timeleft">Temps passé : xx</div>""" % ( self.name,  "\n".join(map(Activity.item_to_html, self.items)))

  def item_to_html(item):
    return "<li>%s</li>" % item
  
# pas bien, global var... mais bon ça fait un petit cache :) 
projects = {}

def get_project_from_gitlab_id(id):
  """
  Récupérer le nom du projet à partir de son id
  """
  if not id in projects.keys():
    strurl = URL_PROJECTS_GITLAB_BY_ID.replace("{{id}}", str(id))
    with urllib.request.urlopen(strurl) as url:
      print("request projects to %s" % strurl)
      data = json.loads(url.read().decode())
      projects[id] = data['name']
    
    
  return projects[id]

def get_activity_from_name(name, arr):
  """
  Récupérer l'activité dans un tableau a partir de son nom
  """
  for a in arr:
    if a.name == name:
      return a
  return None

def get_activity_from_gitlab(start, end):
  """
  Générer une liste d'activité entre deux dates
  """
  activities = []

  # appel api gitlab pour avoir la liste des events
  strurl = URL_ACTIVITY_GITLAB+"&after="+start + "&before=" + end
  with urllib.request.urlopen(strurl) as url:
    print("request activity to %s" % strurl)
    data = json.loads(url.read().decode())
    for item in data:
      project_name = get_project_from_gitlab_id(item['project_id'])

      # type d'actions : pushed to et pushed new
      if item["action_name"] == "pushed to" or item["action_name"] == "pushed new":
        pd = item["push_data"]        
        name = pd["ref"].replace("feature/", "").upper()
        if name == "MAIN":
          continue
        name = name.replace("MASTER", "Merge Git").upper()
        if name == "DEV":
          name = name.replace("DEV", "Merge Git").upper()
        a = get_activity_from_name(name, activities)
        mustappend = False

        if a is None:
          mustappend = True
          a = Activity()
          a.name = name
          
        commit_title = pd["commit_title"].capitalize()
        if("Merge remote-tracking branch" not in commit_title):
          item = "(%s) - %s" % (project_name, commit_title)
          item = item.replace("feature/", "")
          a.items.sort()
          if item not in a.items:
            a.items.append(item)

        if mustappend:
          activities.append(a)
      # TODO : gérer les merge request et faire une section dédiée
      else:
        try:
          print(item['target_type'] +  " action : " + item["action_name"] + " : " + projects[item['project_id']] + " vers " + item['target_title'])
        except:
          print("Oups, erreur pour print")
          print(item)
       

  activities.sort(key=lambda x: x.name)
  return activities

def generate_report(curdate = None):
  """
  Genere un rapport html de l'activité git selon des conventions miist (branche feature/xxxx et commits.)
  Renvoie None, None si le fichier de rapport existe déjà
  """
  if(not curdate or curdate is None):
    curdate = datetime.date.today()
  
  nbweek = curdate.strftime("%V")
  year = curdate.strftime("%Y")

  start_of_curweek = curdate + datetime.timedelta(days=-(curdate.weekday()))
  start_of_curweek_for_gitlab = curdate + datetime.timedelta(days=-(curdate.weekday()+1))
  end_of_curweek = curdate + datetime.timedelta(days=-(curdate.weekday()-1), weeks=1) 

  name = "%s - CR Hebdomadaire MIIST semaine %s" % (WHOIS, nbweek)
  
  original="cr-template.html"
  target="crs/cr-miist-%s-%s-%s.html" % (year, WHOIS, nbweek)

  if not os.path.isdir("crs"):
    os.mkdir("crs")

  # cas des fichiers existants on ne fait rien
  if os.path.isfile(target):
    return None, None

  # copie du template
  shutil.copyfile(original, target)    

  # Read in the file
  with open(target, 'r') as file :
    filedata = file.read()

  # Replace the target string
  start_semaine = start_of_curweek.strftime('%d/%m/%Y')
  end_semaine = end_of_curweek.strftime('%d/%m/%Y')
  
  start = start_of_curweek_for_gitlab.strftime('%Y-%m-%d')
  end = end_of_curweek.strftime('%Y-%m-%d')

  # du templatage de haute voltige...
  filedata = filedata.replace('{{whois}}', WHOIS)
  filedata = filedata.replace('{{start_semaine}}', start_semaine)
  filedata = filedata.replace('{{end_semaine}}', end_semaine)
  filedata = filedata.replace('{{idx_semaine}}', nbweek)

  activities = get_activity_from_gitlab(start, end)

  filedata = filedata.replace('{{activity}}', "\n".join(map(str, activities)))

  # on recopie le résultat avec les substitutions dans le fichier cible. 
  with open(target, 'w') as file:
    file.write(filedata)    

  return (name, target)



def upload_to_gdrive(name, target):
  """
  Envoi du fichier sur GDrive pour mémoire...
  """
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
    allreportofyear = int(datetime.date.today().strftime("%V"))
    for i in range(allreportofyear):
      lastweek = datetime.date.today() - datetime.timedelta(weeks=i)
      print("Rapport semaine %s ------" % lastweek.strftime("%V"))
      name, target =  generate_report(lastweek)
      if name and target:
        upload_to_gdrive(name, target)

    
