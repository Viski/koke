#!/usr/bin/python
"""
Tool for parsing results for KoKe Orienteering division.
"""

import sys
import os
import re
import argparse
import yaml
from datetime import datetime
from difflib import get_close_matches
from heapq import nlargest
from unidecode import unidecode

from simpletable import *

def getCSS():
    return """
table.mytable {
    font-family: times;
    font-size:12px;
    color:#000000;
    border-width: 1px;
    border-color: #eeeeee;
    border-collapse: collapse;
    background-color: #ffffff;
    width=100%;
    max-width:800px;
    table-layout:fixed;
}
table.mytable th {
    border-width: 1px;
    padding: 8px;
    border-style: solid;
    border-color: #eeeeee;
    background-color: #e6eed6;
    color:#000000;
}
table.mytable td {
    border-width: 1px;
    padding: 8px;
    border-style: solid;
    border-color: #eeeeee;
}
#code {
    display:inline;
    font-family: courier;
    color: #3d9400;
}
#string {
    display:inline;
    font-weight: bold;
}
"""

""" Parse results data into python struct"""
def parseResults(data):
    results = {}


    for line in data.split('\n'):
        if len(line.strip()) == 0:
            continue

        # Remove leading position markers and time differences
        res = re.sub(r'^\s*[0-9\.\-]*\s*(\S+\s\S*)\s*((?:[^\W\d]*\s*)*)([0-9\.]*).*',
                     r'\1|\2|\3',
                     line,
                     re.UNICODE)
        if len(res) == 0:
            continue

        (name, team, time) = res.split('|')

        name = tuple(name.strip().split())

        if team.strip().lower() == "ei aikaa":
            team = ""

        time = time.strip()

        # Replace dots with colons, add leading hours, if they did not exist.
        if not time:
            time = None
        else:
            if time.count('.') == 2:
                timeformat = "%H.%M.%S"
            elif time.count('.') == 1:
                timeformat = "%M.%S"
            else:
                print("ERROR! Could not parse time string:", time)
                print("    Erroneous line:", line)
                exit()

            time = datetime.strptime(time, timeformat)

        if name in results:
            print("ERROR! Duplicate result for", name)
            exit()

        results[name] = {"time": time, "team": team}

    return results


def readYamlFile(filePath):
    with open(filePath, 'r') as f:
        return yaml.load(f)

def findNamesFromResults(participants, results, reverseNames, searchForCloseMatches):

    keys = [" ".join(a) for a in results]

    ret=[]
    closeMatches={}

# TODO: Loop through results first. Now we get close matches alse for people that got straight match
    for name in participants:
        if(reverseNames):
            t = (name["first"], name["last"])
        else:
            t = (name["last"], name["first"])

        if t in results:
            n = {}
            n['first'] = name['first']
            n['last'] = name['last']
            n['time'] = results[t]['time']
            n['team'] = results[t]['team']
            ret.append(n)
        elif searchForCloseMatches:
            matches = get_close_matches(" ".join(t), keys, cutoff=0.8)
            if matches:
                closeMatches[t] = matches

    if closeMatches:
        print("      Found close matches:")
        for a, n in closeMatches.items():
            print("         ", n, "=>", " ".join(a))


    return ret

""" Sort list by time. If time isn't specified,
    sort it as last (using current date). """
def sortByTime(results):
    def getTime(k):
        if ('time' in k and k['time']):
            return k['time']
        else:
            return datetime.now()

    return sorted(results, key=getTime)


def timeDiff(reftime, time):
    return (reftime-time).total_seconds()

"""
Rules:

* Time difference of 10 seconds will count as a point.
* If there are less than PARTICIPANT_THRESHOLD participants,
  the winner gets 1000 points.
* If there are equal to or more than PARTICIPANT_THRESHOLD participants,
  the participant finishing in REFERENCE_POSITION will get 1000 points.
    * The winner can't receive more than 1050 points. If winner's points are cut,
      also everyone else who received more than 1000 points will get point reductions
      in the same scale than the winner (same points/second scale)
* Every starter gets at least 500 points.
"""
def calculatePoints(participants, threshold, reference):

    if len(participants) == 0:
        print("Error! Zero participants, won't do anything.")
        return

    def timeToPoints(reftime, time, secsPerPoint):
        timediff = timeDiff(reftime,time)
        # 1 point for every full secsPerPoint
        pointdiff = round(timediff/secsPerPoint, 6)
        points = 1000 + int(pointdiff) #reference gets 1000p
        return points

    def calculate(reftime, time, secsPerPointForWinner = None):
        if not time:
            return 500 # Every non-finisher gets 500p

        # If winner's points are capped to 1050, everyone else with faster time
        # than the reference gets point with the same scale.
        # Everyone slower than reference loses one point per 10 seconds.
        if time < reftime and secsPerPointForWinner:
            points = timeToPoints(reftime, time, secsPerPointForWinner)
        else:
            points = timeToPoints(reftime, time, 10)

        if points < 500:
            points = 500 # Everyone gets at least 500p

        return points


    # Sort participants by time
    participants = sortByTime(participants)

    if len(participants) >= threshold:
        refPosition = reference - 1 # Indexing..
    else:
        refPosition = 0 # Winner is the reference

    refTime = participants[refPosition]['time']

    # Check if best points need limiting
    secsPerPointForWinner = None
    bestTime = participants[0]['time']
    bestPoints = timeToPoints(refTime, bestTime, 10)

    if bestPoints > 1050:
        timediff = timeDiff(refTime, bestTime)
        secsPerPointForWinner = timediff/50
        print("      Limiting largest points. Winner gets one point every",
            secsPerPointForWinner, "seconds.")

    for i in participants:
        i['points'] = calculate(refTime, i['time'], secsPerPointForWinner)
        if i['time']:
            i['timediff'] = int(timeDiff(i['time'], bestTime))

    return bestTime

def resultsToTable(results, series, eventData, config):

    # Sort participants by time
    results = sortByTime(results)

    def getTime(i):
        return i['time'].strftime("%H.%M.%S") if i['time'] else "Ei aikaa"

    def getTimeDiff(i):
        if not 'timediff' in i:
            return ""

        t = i['timediff']

        if(t < 0):
            prefix = '-'
            t = abs(t)
        else:
            prefix = '+'

        (hours, r) = divmod(t, 3600)
        (minutes, seconds) = divmod(r, 60)

        hStr = ""
        mStr = ""
        sStr = ""

        # Add hours if any.
        if hours:
            hStr = str(hours) + "."

        # Minutes must be added always if hours are present.
        if minutes or hStr:
            mStr = str(minutes) + "."
            # Pad leading zeroes, if hours exist.
            if hStr:
                mStr = mStr.rjust(3,'0')

        # Always add seconds.
        sStr = str(seconds)
        # Pad leading zeroes, if minutes exist.
        if mStr:
            sStr = sStr.rjust(2,'0')

        return prefix + hStr + mStr + sStr

    def getPoints(i):
        return i['points'] if 'points' in i else "Error!"

    def constructHeader(series, eventData, config):
        seriesData = eventData['series'][series]
        r = []

        r.append(SimpleTableRow(["Koneen Kerho", "suunnistusjaos", "sarjakilpailu", series.upper(), config["name"].upper(), "", ""], header=True))
        r.append(SimpleTableRow(["", "", "", "", "", "", ""], header=True))
        r.append(SimpleTableRow(["osakilpailu:", "{0} / {1}".format(eventData["event_number"], config["year"]), "", "", "", "", ""], header=True))
        r.append(SimpleTableRow(["rata:", seriesData["track"], "", "", "", "", ""], header=True))
        r.append(SimpleTableRow(["paikka:", eventData["location"], "", "", "", "", ""], header=True))
        r.append(SimpleTableRow(["päivä:", eventData["date"], "", "", "", "", ""], header=True))
        r.append(SimpleTableRow(["järjestäjä:", eventData["organizer"], "", "", "", "", ""], header=True))
        r.append(SimpleTableRow(["rata:", seriesData["length"], "", "", "", "", ""], header=True))
        r.append(SimpleTableRow(["", "", "", "", "", "", ""], header=True))
        r.append(SimpleTableRow(["sija", "nimi", "", "seura", "aika", u"Δt", "pisteet"], header=True))

        return r

    table = SimpleTable(
        constructHeader(series, eventData, config),
        css_class="mytable")

    pos = 1
    for i in results:
        if i['time']:
            posStr = str(pos) + '.'
            pos += 1
        else:
            posStr = '-'

        row = SimpleTableRow(
        [posStr, i['last'], i['first'], i['team'], getTime(i),
            getTimeDiff(i), getPoints(i)])
        table.add_row(row)

    return table

def updatePointsForParticipants(participants, points, eventId):

# TODO: Hyi, mitä looppailua
    for name in points:
        for name2 in participants:
            if(name['first'] is not name2['first'] or
               name['last'] is not name2['last']):
                continue

            if not 'points' in name2:
                name2['points'] = {}

            name2['points'][eventId] = {'count': name['points']}
            break

def getFileNameForSeries(series):
    return "results_{0}.html".format(unidecode(series))

def getFileNameForEvent(number, series):
    return "{0}_{1}.html".format(number, unidecode(series))


def calculateEvent(eventFile, config, resultsDir):
    eventData = readYamlFile(eventFile)
    print("\nParsing event {0}: {1}".format(eventData['event_number'], eventData['location']))

    for seriesName, seriesConfig in config['series'].items():
        print("   Parsing series:", seriesName)

        parsedResults = parseResults(eventData['series'][seriesName]['data'])

        # Search for people from unknown series
        # TODO: Make series selection automatic (with force override)
        unknownPeople = findNamesFromResults(config['unknown_participants'], parsedResults, eventData['reverse_names'], False)
        if(unknownPeople):
            print("\n#############################################################\n")
            print("   Found", len(unknownPeople), "participants with unknown series:")
            for i in unknownPeople:
                print("      ", i['first'], i['last'])
            print("\n#############################################################\n")

        correctPeople = findNamesFromResults(seriesConfig['participants'], parsedResults, eventData['reverse_names'], True)
        bestTime = calculatePoints(correctPeople, seriesConfig['participant_threshold'], seriesConfig['reference_position'])
        updatePointsForParticipants(seriesConfig['participants'], correctPeople, eventData['event_number'])

        # Add people from wrong series and set their points to X
        for wrongSeriesName, wrongSeriesConfig in config['series'].items():
            if wrongSeriesName == seriesName:
                continue

            wrongPeople = findNamesFromResults(wrongSeriesConfig['participants'], parsedResults, eventData['reverse_names'], False)
            for i in wrongPeople:
                i['points'] = 'X'
                if i['time'] and bestTime:
                    i['timediff'] = int(timeDiff(i['time'], bestTime))

            updatePointsForParticipants(wrongSeriesConfig['participants'], wrongPeople, eventData['event_number'])

            # Merge results
            correctPeople = correctPeople + wrongPeople

        #updatePointsForParticipants(seriesConfig['participants'], points, eventData['event_number'])

        htmlPage = HTMLPage(tables=[], css=getCSS())
        htmlPage.add_table(resultsToTable(correctPeople, seriesName, eventData, config))

        outputFile = getFileNameForEvent(
            eventData['event_number'], seriesName)
        outputPath = os.path.join(resultsDir, outputFile)

        print("      Writing event results to:", outputPath)
        htmlPage.save(outputPath)


def calculateTotalPoints(config):

    max_events = config['max_number_of_results']

    for series in config['series'].values():
        for name in series['participants']:
            if not 'points' in name:
                continue

            # Strip X's and find the N best points from results
            strippedPoints = dict((k, v) for k, v in name['points'].items()
                                  if isinstance(v['count'], int))
            bestEvents = nlargest(max_events, strippedPoints,
                                  key=lambda x:strippedPoints[x]['count'])

            # Sum the best N points, and mark the used events
            name['total_points'] = 0
            for event in bestEvents:
                strippedPoints[event]['used'] = True
                name['total_points'] = name['total_points'] + strippedPoints[event]['count']

def emptyRow(numCells):
    return [ "" for i in range(numCells) ]

def updateRow(row, data):
    for k, v in data.items():
       row[k] = v

    return row

def outputIndexPage(config, resultsDir):

    htmlPage = HTMLPage(tables=[], css=getCSS())

    rowWidth = 3
    lastCell = rowWidth - 1

    rows = []
    headers = []
    headers.append({0: "Koneen Kerho ry", 1: "Suunnistusjaos"})
    headers.append({0: config['name'], 1: "sarjat", 2: config['year']})

    for h in headers:
        rows.append(SimpleTableRow(updateRow(emptyRow(rowWidth), h), header=True))

    for series in config['series'].keys():
        data = { 0: "<a href=" + getFileNameForSeries(series) + ">" + str(series) + " sarja" + "</a}"}
        rows.append(SimpleTableRow(updateRow(emptyRow(rowWidth), data)))

    htmlPage.add_table(SimpleTable(rows, css_class="mytable"))

    outputFile = "index.html"
    outputPath = os.path.join(resultsDir, outputFile)

    print(   "Writing index file to:", outputPath)
    htmlPage.save(outputPath)


def outputSeriesTables(config, resultsDir):


    def constructHeader(series, config, maxEventNumber):
        r = []
        rows = []
        numEvents = config['number_of_events']
        rowWidth = numEvents + 4
        lastCell = rowWidth - 1

        rows.append({1: "Koneen Kerho ry", 2: "Suunnistusjaos"})
        rows.append({1: "Sarjakilpailu", 2: config['year']})
        rows.append({1: series.upper(), 2: config['name'].upper(), lastCell: "{} parasta".format(config['max_number_of_results'])})

# TODO: Add links to only to existing events
        lastRow = {1: "nimi", lastCell: "yhteensä"}
        for i in range(numEvents):
            eventNumber = i+1
            eventFile = getFileNameForEvent(eventNumber, series)
            if eventNumber > maxEventNumber:
                lastRow[i+3] = eventNumber
            else:
                lastRow[i+3] = "<a href=" + eventFile + ">" + str(eventNumber) +"</a}"

        rows.append(lastRow)

        for row in rows:
            r.append(SimpleTableRow(updateRow(emptyRow(rowWidth), row), header=True))

        return r

    def outputResults(participants, rowWidth):

        def getPoints(p):
            if not 'total_points' in p:
                return -1
            return p['total_points']

        sortedParticipants = sorted(participants, key=getPoints, reverse=True)

        rows = []
        r = []
        pos = 1
        lastCellIndex = rowWidth -1
        maxEventNumber = 0

        for name in sortedParticipants:
            if not 'total_points' in name:
                break

            temp = {0: pos, 1: name['last'], 2: name['first'], lastCellIndex: "<b>{0}</b>".format(name['total_points'])}

            # Fill in points
            for k, v in name['points'].items():
                if k > maxEventNumber:
                    maxEventNumber = k

                # Graying out unused points
                if not 'used' in v:
                    field = """<font color="gray">({0})</font>"""
                else:
                    field = """{0}"""
                temp[k+2] = field.format(v['count'])

            rows.append(temp)
            pos = pos + 1

        for row in rows:
            r.append(SimpleTableRow(updateRow(emptyRow(rowWidth), row)))

        return r, maxEventNumber


    numEvents = config['number_of_events']
    rowWidth = numEvents + 4

    for series in config['series'].keys():
        htmlPage = HTMLPage(tables=[], css=getCSS())
        rows, maxEventNumber = outputResults(config['series'][series]['participants'], rowWidth)
        headers = constructHeader(series, config, maxEventNumber)
        headers.extend(rows)
        htmlPage.add_table(SimpleTable(headers, css_class="mytable"))

        outputPath = os.path.join(resultsDir, getFileNameForSeries(series))

        print(   "Writing series results to:", outputPath)
        htmlPage.save(outputPath)

def scpResults(config, resultsDir):
    if not "scp_destination" in config:
        print("Unable to scp results, scp_destination not specified in config")

    print("Copying results to", config["scp_destination"])
    os.system("scp {} {}".format(
        os.path.join(resultsDir, '*'),
        config["scp_destination"]))

# Main

# Parse cli parameters
parser = argparse.ArgumentParser(epilog = __doc__)
parser.add_argument(
    'config',
    help = "Configuration file in yaml format")
parser.add_argument(
    '-c',
    action = "store_true",
    dest = 'scp_enabled',
    help = """If specified, parsed result files will be copied to
'scp_destination' specified in config file.""")
parser.add_argument(
    '-r',
    dest = 'results',
    help = "Results folder")
parser.add_argument(
    '-s',
    dest = 'sources',
    help = "Folder containing the event files in yaml format")

args = parser.parse_args()

if args.results is None:
    args.results = os.path.join(os.path.dirname(args.config), "results")

if args.sources is None:
    args.sources = os.path.join(os.path.dirname(args.config), "sources")

os.makedirs(args.results, exist_ok=True)

config = readYamlFile(args.config)

for filename in sorted(os.listdir(args.sources)):
    if not filename.endswith(".yaml"):
        continue

    filepath = os.path.join(args.sources, filename)
    calculateEvent(filepath, config, args.results)

calculateTotalPoints(config)

outputSeriesTables(config, args.results)
outputIndexPage(config, args.results)

if args.scp_enabled:
    scpResults(config, args.results)
########################################################333

# Check for people with currently unknown series
"""
unknown = findNamesFromResults("unknown", names, results, args.reverseNames)
print("\n\n#############################################################\n\n")
print("Found", len(unknown), "participants with unknown series:")
for i in unknown:
    print("   ", i['first'], i['last'])
print("\n\n#############################################################\n\n")

# Find people from correct series and calculate their points
correctPeople = findNamesFromResults(args.series, names, results, args.reverseNames)
correctPeople = calculatePoints(correctPeople, args.series)

# Add people from wrong series and set their points to X
seriesList = ['long', 'short']
seriesList.remove(args.series)
wrongPeople = findNamesFromResults(seriesList[0], names, results, args.reverseNames)
bestTime = correctPeople[0]['time'] if correctPeople else None
for i in wrongPeople:
    i['points'] = 'X'
    if i['time'] and bestTime:
        i['timediff'] = int(timeDiff(i['time'], bestTime))

# Merge results
res = correctPeople + wrongPeople

# Print results
print("Results:\n")
prettyPrint(res)

# TODO:
# * osakilpailutietojen täyttö automaagisesti?
# * sarjapisteiden laskenta kanssa?
"""
exit()

