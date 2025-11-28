---
tags:
  - email-automation
  - workflow-creation
  - gmail-trigger
  - email-management
  - productivity-tool
---

in this video we're creating an email agent that is literally going to run your email account this is so freaking

cool take a look at this so when an email comes in to your Gmail account just like this email came in right here

we're going to automatically label it so we're going to sort all of your emails into specific categories like for

example promotions or social tab or sales or receipts or recruitments or

personal and then we're going to take whatever action it is that you want it to take so for example example in this

particular workflow I had a personal email come through like you can see here it sorted it as personal and then it

created a followup email where all I have to do is just approve it and click Send so we can create drafts in this

case we can reply to messages automatically we can send messages or

forward them so for example if we have receipts coming through maybe we want to for that over to our accountant we can

go ahead and do that if there's sales we can draft a reply if there is a social message we could for example create a

summary of that post into Google Sheets so that we can just quickly skim through all these emails and if it's a promotion

well maybe maybe for example you don't want that and you just want to mark it as red we're going to go ahead and build this system out it's super simple but it

is incredibly powerful and the whole idea here is to essentially free up your inbox so that you don't have like an

overflowing inbox of like tens of thousands of emails so we'll trim it down so that you can stay focused organized and get the most out of your

email just obviously being super productive so if that sounds like something you guys are interested in we are going to be building this out today

in this particular video if you guys are interested in downloading These Blueprints all you have to do is hit these three dots and import the file in

the blueprints will be down below in the description for free for you to download and you can get this exact workflow in a

matter of a couple seconds but we're going to be building this out together right now so the first thing we need to

do is set up a trigger inside our NN account and what that trigger is is a essentially saying every time we receive

## Creating the workflow

a new email in our inbox we need to go ahead and start this workflow and so the first trigger that we're going to choose

## Gmail trigger

is Gmail specifically this on message receive trigger and there's a couple

things that I want to set up here to get this operating properly so we have

credentials to connect with now if you haven't done so already just go ahead and create credentials to log into your

Gmail account you can just simply click this sign in with Google because I've already actually done that I'm just going to close this and move on now the

next thing that I want to talk about here is polling times because this is probably one of the most important things about this whole entire operation

if you don't get this right it can be pretty costly so effectively what polling means is that this scenario and

I'm going to switch over to my white Blackboard here this scenario is going to run every single time that n8n wants

to access your Gmail account right so a poll is just sending a request being

like hey is there any mail that's currently available for us to process this workflow and regardless of whether there

is right mail or regardless of whether there isn't mail it's still going to

cost you money to do this poll and the problem is if you're doing it at a one minute interval that means you're going

to be firing off 1,440 different operations every single

month right so that's obviously a lot and your intro plan might only have 2,500 so literally within Maybe two days

you're going to go through this so we need to slow down this polling so that you're not spending as much money and

how we do that is by slowing down the Cadence here so every hour is a bit slow

every minute is a bit fast so we're going to choose this custom expression here and what I want to do is enter in a

Chone expression so we can just search up Chone expression n8n and uh let's go

to their actual documentation here and we can just copy in something like this so maybe like we'll do every 5 minutes

or maybe every 10 minutes or something like that I'm just going to stick with five for now what this is saying is that

instead of every minute now we're going to be sending it off at every five minutes we're going to be pulling right which will cost an operation and so that

is more or less it we can go ahead and save this if you guys want to you can uh

filter it down and add in additional things here but to me that looks good

I'm actually just going to fetch this data and see if there's anything we can see that there's uh actually I think my

face is blocking that but there's no uh there's no there's no results being found here so that's okay we've

officially set up our our first uh trigger here I'm going to go ahead save this workflow and just to start this

trigger I'm actually going to load in some data so I'm going to go into my inbox here and I'm just going to send

myself a message so that way we have test data to work with so circling back

into our nadn and environment I'm going to test this and we're going to see if in fact

that email that we just sent off was uh loaded in properly and we can see that

it was right snippet is test and test is the subject and I sent it off perfect so

what I want to do is just in the spirit of making this as quick as possible I'm going to pin this data what pinning

means is that every time the scenario is run it's going to use this sample data

so that I don't have to go back and forth every single freaking time and go back to Gmail and send an email off it's

just going to speed up the workflow significantly so the next thing that I want to do here is I want to do

sentiment analysis and we're going to use the text classifier here okay so

## Classify the email for labels

we'll go ahead and use text classifier and essentially what's going on here is we're going to pass in two things I want

to pass in the subject of the email and I want to pass in the email body and

we're just going to ask Chachi BT like hey you know is um like what do you

think this email belongs to like what category is this a personal email primary promotional social and we can

just add as many labels down here as we want here so this is just going to effectively use AI to determine what the

email is right so I'm just dragging in the subject here you can go to like schema or table or Json but I'm just in

schema right now and I'm literally just dragging this over into the block here so I'm going to copy this and just move

it into the subject line and it says json. subject here this is essentially

the exact same way this is just this particular subject line written out and then we have the email body which is the

um the snippet over here so we're going to paste that in and we can essentially

create as many categories as we want right so maybe I'm going to do like

promotions and then I'm going to do social I'm going to do personal maybe I want to

do sales Recruitment and um that looks good for

now maybe yeah I I think I'll just stick with this and we just need to write like a short little description of what this

is so this is any email looking to sell me things social is any email from a

social media site like YouTube or Facebook uh or Instagram and so on and

so forth okay sweet so we have our categories promotions this is anything uh anyone looking to sell me things

social any emails from a social media site like YouTube or Facebook personal an email sent from a friend or family

member um sales is anything regarding like client document sales all that kind of stuff recruitment is anyone looking

for a job or to join our team and receipts are transactional emails so this looks good to me and so essentially

all we need to do to make this work properly is we need to attach a model and what this is saying is like we have

this built-in function here to classify text but in order for us to understand what text is we need to have some form

of reasoning and that reasoning is going to come from an AI model the cool thing about Ann is they allow you to choose

whatever AI model that you want so if you like for example anthropic you can use that if you want deep seek you can

use that or Google Gemini or whatever and for the purpose of this tutorial I'm going to be using chat GPT and GPT 4-

mini is good enough for me there's literally nothing else that I need to add here so we're good to go and we can

move this over and um we can give this a test run and just take a look and see

what it comes up with for this so I'm going to click back into this and it

looks like uh looks like uh oh that's weird it

didn't actually give me a result there I'm just going to take a look at the executions tab to see what happened here

so we can take a look at the past runs in this particular module here and just

see what it came up with so potentially it just came into the promotions tab but

it doesn't actually look like there was an output for this so that's a bit interesting I just want to see there was

a uh input in here right and so maybe it just can't really determine you know

between these we could also add like a miscellaneous tab in here too so miscellaneous and

anything that doesn't fall within the other categories okay cool and we can

try this one more time just to see if that potentially works and perfect so we can see here

that it did work in fact this time and and uh yeah so it went down the miscellaneous tab here at the last you

can see that it's green at the bottom there and so that's the first part is we're just classifying which category do

we actually want to put this email into right and so from there we're going to create labels like personal right I'm

## Creating labels for gmail inbox

also going to add another one in here which is like recruitment for example and I can add in receipts and what else

do I want to do in here recruitment receipts sales

miscellaneous sales and

miscellaneous and everything else is just going be used like the default categories within within Gmail so we'll

go ahead and set this up the next thing I want to do is enter in Gmail here and we're going to add a label to a message

so we can search by um label and we can just add it to the particular message

here or the thread whichever one works for you so I'm going to go ahead and I'm just going to add it to the message here

and effectively all we need to do is just add in the particular ID here and

you'll see that there's no data right and the reason why there's no data is because um right now at the time uh we

haven't ran the Gmail module through the promotions but if we came into miscellaneous for example and we did the

same thing then all of a sudden we could see the data so let's go ahead and add

this for recruit or miscellaneous just because right now it's only past the miscellaneous um category so we're going

to go ahead and add to this and now all the data is on the left side here right

and so I'm going to go ahead and add in the message ID here which is just right

here so we're going to drag that over to the message ID and we can choose the right category which is miscellaneous

here and this is going to automatically go ahead and Mark that as miscellaneous we can go we can try this out here I'm

just going to delete this test the workflow and if we Circle

back this should should be categorized now as miscellaneous and it's also going

to be in our miscellaneous folder here as well so this is working so far now we

can go ahead and do the exact same thing for all these other modules here I'm just going to duplicate this up top and

we're going to change this to Promotions so add a label here as

promotions and there's a bit of repetitiveness here obviously because we're going to have to go ahead and do

this again I'm just hitting com control or command D to be able to duplicate these over and over and over again and

I'm going to go ahead and pause this video and come back when these are all done so I've gone ahead and I've added

all of these additional um labels here just so that you guys didn't have to sit

here for like the last five minutes of me frantically trying to create these but I'll just go go over these and show

you a couple so we got like category promotions and we got category social here and then we got category we have

the sales label which is the Custom Sales label that we created here and so on and so forth all the way down the pipeline right and so essentially from

here on out now what we can do is we have emails they're coming in they're all being categorized right this is so

freaking cool all of a sudden you have an inbox right now that is going to be completely organized you're going to be

staying on top of everything you're going to know exactly when an email is coming in where to find in what category

it's just going to be so much nicer to keep everything organized and so the next thing that we can do here is we can actually actually automate the process

## Mark emails as read

of dealing with these emails right like for example maybe I want to automatically send a message back to

this person and handle some common sales inquiry or maybe if it's a personal

message I want to create a draft but I don't want to send it off immediately and so we can go ahead and do that so let's let's start first of all with the

promotions tab up here so we have this pinned data here I'm going to go ahead and I'm going to edit edit this just so

that we can run it down the promotions tab so the snippet here I'm just literally going to write in um this is a

promotional email selling you things and the reason I'm saying this is just

because I want the text classifier to be like oh this is something that's selling

me things so it can go down this path why that's applicable here is because I want it to go down here so we can test

this out right so the first thing I'm going to do is I'm going to add in a Gmail and maybe we just want to mark it

as red right so I'm going to to Mark a message is r and you can see here we

don't have any input data we'll go ahead and unlink this and we'll test this

workflow it's going to classify it now run it down the promotions Tab and the reason it went down here again is

because I just put this snippet in here being like this is a promotional email just giving it some mock data and now we

have all the data on the left side here so I can quite simply just come in here

put the ID of the message message here and then Mark it as red right and so now

if we come back into our inbox here I'll actually mark this as unread so we can

test this out and run this one more time let's give it a

shot sweet and so automatically within Gmail might take a couple seconds here

but it should Mark this as red right and there we go so that's

cool we can mark all promotionally and this is just an example I mean you can do that with promotions you don't have

to do it but this is just one of many use cases that you could have here and so the next thing here is social tab

## Summarizing emails

maybe for an instance we just want to summarize these emails and we put want to put them into a Google sheet here so

we can go ahead and do that we're going to test this data Again by just changing this and saying this is a social

email from YouTube and we're just saying that again again to run down the social path I'm going to exit out of this and

we can set up another module here which is open Ai and I want to

summarize so I'm going to message this model here and just ask it to summarize

everything now if you guys haven't done so already for this to work you'll need to uh create a connection here and so in

the open AI module you'll need an API key all you need to do is go to platform open

AI uh oops that is not how you spell platform so we'll go to platform and

then log into our account here and once you're signed in we can go

to dashboard API keys and then just create one right here and then once you

create it then you can go ahead and if I just like go like test here and were to

grab this I could just paste that in here just make sure that you add $5 to your account otherwise you're not going

to be able to access uh chbt so in order to add $5 to your account you can just go into the profile Set uh here go into

billing and then add $5 and you're good to go and once we're back inside what we can do is just say um and just continue

on with this workflow of summarizing the email that we got in here so for example

maybe I just want to use 40 mini as the model 4 o

mini we'll wait for this to load and we're going to add in a couple messages here so the first one is just going to

be a system message telling chat GPT what to do so system message is

essentially like you're essentially providing a um just overview of what it

is you're looking for chat to do so you're an

intelligent bot at summarizing summarizing emails and that

is good enough and we're going to add in a user message this you can think about user message is like the input of this

message and all we have to do here is load in data currently we don't have anything so we'll go ahead and test this

workflow again it's going to go down the social path and now we have everything

on this side here so the text is going to be the actual email text that we have

here so we'll we'll actually add in subject and email body this is good for

me the snippet is the body here so we'll paste that down here and the subject is

just right over here so we'll go ahead and copy that in here as well and obviously this is like not going to be

super easy for it to summarize because well I mean it's like a literally a

one-word email I'd be like shocked if chbt could make it any more concise than that but we can go ahead and just test

this out and at least get some form of response here to see it comes up

with okay cool and so we have the content here which is the

output and so in a traditional email and not just one that I threw together in

two seconds with test in there it would actually go ahead and in the content section here it would summarize that

particular email and so we can take that summary and we can add into a Google sheet right so I've got already gone

ahead and done that so I'm just going to go into sheets here sheets. google.com and I have

created um this here this just handy nice little

Nifty spreadsheet so we have ID of the email the date subject line summary and snip it and so we can just go ahead and

dump that in here just as an example so we'll choose Google Sheets and I'm going to add or update a

row we're going to choose this option and we just want to connect into this particular sheet here so again if you

haven't done so already you'll have to create this connection and just sign in with um Google one more time just to

give it access to not only your Gmail account but also your Google Sheets as well I've already done so so I'm just

going to skip over this and we can then go ahead and select the sheet

here and for me it's email summary NN and you have a lot of different

operations here like you could create you could append I think actually

yeah we'll just we'll just choose Creator append for now and what this means is that appending is just adding a

row and updating is hey if this row already exists then instead of creating a new duplicate let's go ahead and just

update the existing row on file and so sheet here is just sheet one it's the tab down here right by default it's just

listed as sheet one and the next thing that it's going to ask for is the column

to match on and the column to match on is essentially saying like if we want to update something and this isn't

necessary for this particular automation but if we want to update something it's like how do we know what to update it we

need to find a unique identifier and that unique identifier will be the ID of the email because that will always be unique and it's never going to be um the

same across emails so we'll go ahead put the ID in here and choose the column to

match on which is if we want to update something it's going to be based on the ID if we find the same ID for the date

we can change this from a fixed field to an expression expression just means that we can add in custom Fields like this

right and we're just going to hit this the the cly braces twice here so I'm

just typing this in right so I'm just typing it in twice and then we're going to hit dollar sign now and this is going

to give us the result down here which is the exact second that this was processed subject line we can get from the

particular email which is down here so I'm going to drag that in summary uh is going to be from chat GPT

which is up here in the content section and then we have the email snippet which is the original snippet

here over here so that's just one example we can go ahead test this out and see if this worked properly so we're

classifying it we're sending it to Social and then we're just adding it in to this particular Google sheet and

there we go right okay cool on to the next thing maybe if it's a personal email we just want to create a draft

right maybe for personal matters you don't want to automatically send an email you just want to have a quick once over right and so we can go ahead and we

can do that for the personal email here we're actually before we test this out we're going to go back to the trigger

and just update this and say this is a personal oops this is

a personal email from a friend and we'll save

this and we'll create a draft here so Gmail

and create a draft sweet and the resource again is going to be

## Create a draft email

draft and we're going to create that and the subject line can be whatever it is

that you want actually I don't think this is the right one so we'll go ahead and create a draft here so I'm going to

type in Gmail here and create a

draft awesome and from here on out we don't even need to

add in a subject line just because we're going to be replying to the thread here and the message that we want to create

we're going to have to use chat GPT to do so and one more option that I want to do here is I just want to add in thread

ID and this thread ID is essentially more or less going to be the thread that we reply to so I don't want to just

create a generic draft I want to reply specifically to this message and so that

looks good to me we'll just test this out first of all so we can load in data and it looks like we're drawing an error

from this module here so I'm going to disconnect it and we're going to give it a shot again and going to move this out

here duplicate this by hitting command D or contr D and we're going to link this

back together you're an intelligent bot at replying to emails

and we have the system message done for the text the user message which is just

the input here's the email to reply to and that looks good to me and then we

just need to do one last thing is we need to format this message properly so

I'm going to go ahead and I'm going to choose assistant so you can think about an assistant message is just like the output right so how we're how we want

the data to come out as and so we can format the data in any way that we want in this assistant message so user

message is the input assistant message is the output and I'm just going to say please format the data in Json format

Json format is essentially like literally just this on the side you can see it it's just easy we can drag and drop it so we want it to be in the same

format as as the rest of the data and then done and so we'll put a CO in here

and more or less um I'm just going to create Json this will be in the uh

blueprints for free down below if you guys want to actually just literally copy and paste it but essentially this

is the format of Json data we can do um subject line we're getting two pieces of

information back we're getting subject line and we're getting email body right

and so this is our data it's just going to provide us with when it it replies back to this subject line even though we

don't technically need that but we're going to duplicate this for the rest of the modules and then email body back as

well so it's going to give us this so we can easily Plug and Play that into the next system if you guys also want you

could just go into chat gbt and it's like hey please create me um please create

me please create me Json data to reply back to an email include in

there um subject line and email body and it should just actually create this Json

for you right and these are just this is exactly what I just did except I just

had slightly different uh Keys here and it doesn't really matter I mean you these keys are

subjective they can change whatever you want them to be and it's just giving sample data here you could go ahead and delete that and that's exactly what I've

done here so let's go ahead let's try that out and then program the rest of

this back in we can take a look and see the uh response and this is actually

giving us text back which is not good because we don't want it as like Json

data in text format we want Json data like this so we can click and drag and drop it in but this is like combining

multiple things into a text so this is like multiple data types that you're mixing in to each other and so how we

remove that is we just output the context as Json data and instead of it coming back Json data and text is going

to come back in actual um Json data so we'll go ahead and test this one more

time and then look at the response and now we have this beautiful Json data

where we can just literally copy and paste subject line and email body back in so now when we go ahead and we

connect this email back in to this workflow here all we need to do is just

copy the email body message in here and then it'll give us a draft reply hey

there thanks for reaching out I'm glad to hear from you how have you been let's catch up soon and um lastly we just need

to add this email thread in here and that's going to be from the first module down here which is the Gmail trigger

right and we have the thread so we're going to pass this in and that note that's telling it hey let's reply

to this particular thread not just some random draft email somewhere on the account but actually reply back to this

so that looks good to me we can go ahead and we can give this a shot oh it looks

like there's an error here and we can put in subject line I guess too which is

um oh weird okay it we got disconnected from the data source so I'm going to have to delete that for now

and then just paste it back in here so essentially what I did there was I ran it one more time just that we could get

the uh the data here to map it in and so I'm just going to paste the subject line back in there and we are good to go we

can go ahead and test this out and it should actually create a draft reply to that email thread so

workflow has been successfully executed let's go ahead refresh this page

and now we have the draft right and so there's a couple things to this number

one is that we probably want a two email and also we just want to make sure that

we're actually including the name of the person and we're including your name down below as well so let's go ahead and

do that so first things first in the Gmail module we're going to add option and it's going to be to email and this

is going to be the email that we want to send to and we can get that email from

uh right here so essentially it's going to be the from email address

here and then from there we just need to go into chat gbt and just make sure that

we're saying in the user message which is the input we're saying hey here's the subject line here's the email body we're

just going to say who this from this email is from colon and we'll go ahead and pass in the Fram section

here and in the actual system message Mage which is like giving General context to chbt I'm going to say please

sign off on all emails as follows and it's going to be

best jono and then we can go ahead and try this workflow out one more time and

see if in fact those changes were made and and everything looks good now so I'm

going to go ahead and refresh the page

here and I'm just going to actually delete this draft and try it one more

time because I don't think you can have two drafts on the same

email Okay cool so let's go back let's take a

look and here we go so we're replying back to the person hey thanks for reaching out have you been let's catch

up soon and so it's now not saying like the name or anything like that which is pretty nice now for whatever reason it

didn't even include the best jono in there so that's a bit strange here let's

just take a look um and anyways you you can play around

but with this and essentially get it to work as you want and you can add in additional system messages like hey don't include it all in one line and

separate also separate paragraphs by line breaks and so so on

and so forth but just for the purpose of this tutorial I'm not going to spend too much time on that because that's not you

know necessarily want to want to spend a lot of time on so the next thing is sales so maybe in this instance we can

just reply back to people so we're going to go ahead and we're going to choose edit here and I'm going to say this is a

sales email from a client we'll go ahead and save that and we can run this now and

it's going to go down that sales path here and maybe on sales we just want to

## Send email

automatically send a message to the person right so instead of creating a draft we can just go ahead and send that

over I'm going to duplicate these down one row to the sales section here and

same kind of deal I'm going to open this up and just say you're an intelligent bod replying to sales

emails and we'll just say sign off at the bottom here's the message that all looks good to me and we can go ahead and

instead of creating a draft we're going to um send a message

and we'll just go ahead and and include the subject line and email and all that kind of stuff from from chbt but you can

see here again that the data has been removed so we have to unfortunately go back and delete this test it one more

time to actually get all this data from Chad GPT and all that kind of stuff in order to be able to send off that

email okay perfect and from here on out we can just map in

the rest of the variables two is going to be here and we have the uh subject

line and everything else which is up here right so looks good to me the only

thing that I want to do is I want to make sure that we don't append the NN attribution because if we send off an email and it's like this email is from

NN obviously it's not going to be a good touch so let's go ahead and delete that save this and give this a shot so I'm

going to test the workflow and see how this works okay everything's running and it

looks like we've actually gone ahead and sent that email so I'm going to go ahead and refresh the

page and it looks like we sent the message but we didn't actually send it

to uh like on that same thread here which is problematic so what I'm going

to do is I'm going to delete this I'm gonna add another Gmail module and it's going to be thread so we're going to

be replying to a message and let's try this one more time so we're going to reply message ID we're getting from

Gmail and the message we're getting from chat GPT which is the email body and we just want to make sure that

we remove that a pen from NN and that looks good to me this should work out of the box this time so we'll go ahead and

try this out and perfect so we'll

refresh and we can see here that now we have replied to it saying hey thanks for

your email blah blah blah blah blah right and so that's how you can actually automatically send emails instead of

just creating a draft and then let's say for recruitment for example actually you

know what I'm just going to skip over recruitment because these two are going to be pretty much the same for receipts

maybe we want to forward this off to somebody right and so how we can do that is we can just come back in and we can

add in a send email and maybe in this instance we're just going to forward

## Forward emails

this over to our accounting department right so as simple as that we can just

send it off instead of having the two being from who sent the email right so

if somebody um sent a receipt over you don't want to reply back to that person you want to forward that over to your

accountant so maybe just in this case I'm going to pretend like you know this is my accountant's email even though

it's essentially the same email here but you know this is acting as the accountant email and we can go ahead and

just enter in forward here and also in the body as

well and yeah this is just going to forward that email that came into your account straight over to somebody else

so let's go ahead and change this to receipts now so I'm going to come into

this test data here and say this is a receipt email from a

software save this and we can test this workflow one more time okay sweet and then that's been

forwarded over we can take a look at our inbox again and just see that you know we have

this uh forwarded message here it did come up blank there's no data and that is just because it wasn't mapping in the

correct fields and we can come back here and just change that so we'll say that

the subject line is from the initial email here which is down here awesome

same thing with the HTML here we're just going to say this is the snip

it and then that looks good save this test it out

again Circle back refresh and here we go right so now we

have the the the message being sent there and then finally we have miscellaneous and yeah you could

essentially do whatever it is that you wanted with this I mean um for

me like yeah I probably this is just more like a catchall for you if it

doesn't fit into any of the other responses but uh yeah there's a lot of stuff you could do here I mean for

example you could just send off like a twio message or a telegram message uh to yourself being like hey you have a new

message here so we could do like telegram for example or tlio and just be like hey when this message comes in if

it's important then send it off right and so I'm not going to go through the process of building that out but I think that that's just like a cool idea of how

you go about setting this up so you have multiple different ways of dealing with many different messages here right so

for example just going through this again if it's a promotional email maybe you just mark it as R if it's a social

email you summarize it and put into a Google sheet if it's a personal email maybe you create a draft so that you can

reply back and maybe even you send a text message here being like hey this draft has been created let's send it off

if it's a sales email maybe you reply immediately if it's a receipts email maybe you forward it to somebody and if

it's a miscellaneous or whatnot maybe I don't know you can do whatever it is that you want and so this is just a

great way to essentially have something like NN manage your entire inbox here

for you so that as soon as emails come in they're being labeled properly they're being responded to you don't

even need to do it yourself you don't need to hire somebody to do it it's just automatically done for pennies on the dollar using naden so I hope you guys

found value in this video if you did make sure to like and leave any comments if you have questions and I'll see you

guys in the next one thank you very much for watching and bye-bye