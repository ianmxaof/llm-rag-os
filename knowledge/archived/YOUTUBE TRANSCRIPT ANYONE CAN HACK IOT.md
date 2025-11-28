---
tags:
  - iot-security
  - ethical-hacking
  - iot-devices
  - cyber-security
  - vulnerability-analysis
---

welcome everyone uh my name is Andrew bini and I am here today to both

convince you and show you that anyone can hack iot devices so in the talk

today I'm hoping to both convince you that and I'm also going to walk you through a methodology that you can go

take home uh buy a cheap consumer iot device and hopefully hack it uh before we get into the actual specifics of that

I actually just want to start with a really quick joke and that joke is uh the s in iot stands for security has

anyone heard that joke before here it's one that I hear yeah see some people are hearing it it's one that I hear tossed

around the cyber security Community uh and usually when I hear that joke it's actually by folks that don't work

specifically uh in iot or embedded security um but as someone who actually

has a background working in industrial iot devices and embedded devices I Won't

Say I'm not salty about it I'll actually put my hand up and be the first to say that it is a welld deserved D

joke so the thing about that joke is and we can all you know have a laugh at iot devices and their lack of security but

the reality is if you you know check out and look out how many estimates for iot

devices there are connected in the world right now you'll see uh greater than 15 billion you know estimates that's almost

two per person of iot devices and in addition to that uh we're expecting

there to be a big surge of iot devices because of AI and machine learning how they're going to to be used for Edge

devices and it's estimated looking at the projections there could be 30 million by or 30 billion Sorry by the

end of the decade so that is a lot of things to secure and these are

everywhere so it's not like they're just in our households from you know smart cameras to even smart toilets uh these

are also in critical infrastructure they're in our cars they're essentially everywhere

nowadays so one of the things that I kind of thought when I was starting to get interested in iot security is

there's so many devices and in addition to that uh there's this agreed upon kind of thing in the security community that

iot devices are not secure so I figured there would be uh a lot of people doing

iot hacking and the Cyber criminals are definitely taking advantage of this they

love uh finding vulnerabilities and iot devices and adding them to their botn Nets or using them for initial access uh

but my experience was in the ethical hacking Community when I started meeting hackers and things like that and asking

them if they hack iot devices uh a lot of times the answer was no and that was kind of reaffirmed today too I've had a

a a booth here where we've been doing iot hacking and I had mostly beginners who had never done it and it was awesome to teach them

that so one of the things that you know I I when I ask people why aren't you doing iot hacking there's a few

misconceptions that I hear about it and uh I just want to try and dispel some of those so the very first one is that it's

too expensive so you need to buy expensive gear you need like you know an oscilloscope or like a microscope or

expensive tools to get into it um when you're starting out and this is a reality you're probably going to need to

buy the devices you want to hack on uh and then addition there was really a a large lack of affordable training uh

when I was looking to learn even you know five years back it was like $5,000 for a course A lot of them were in

person and then the second misconception I hear is that it's very complicated you need to like have an engineering degree

you need to know about Electronics you need to about Hardware circuits um all of that stuff you need to know about

special protocols in addition to just the you know normal things that you need to know about hacking uh and in my

opinion you know some of these are true there is some truth to it but I actually think there are ways that you can

actually learn uh to hack iot devices commercial iot devices off the shelf

without spending that much money and there is a lot of great resources to learn how to do it for free or for very

limited amounts of money okay so I've been chatting for a little bit I just wanted to give a quick

intro to who I am and why I know a little bit about iot and iot security so

my name again is Andrew bini I go by digital Andrew on the socials my background is actually in electrical

engineering so before I got into cyber security I did a lot of work actually designing embedded devices and

Industrial iot devices so that's a little bit where I learned about it not specifically in security but just

actually you know designing the devices that we use I now work as a content creator at

TCM security so there I am the creator of our iot hacking course it's a beginners iot hacking course and I also

created our practical Junior iot tester certification uh and if you do want to link up with me you want to copy of

these slides you want to see what I'm working on I got lots of free blog resources or anything like that check out my

website so a little bit of motivation for this talk um I one specific goal and

that is to provide you with a methodology specific tools and knowledge to vine vulnerabilities AKA hack in

commercial iot devices and I have a couple messages here from some of my previous students just to give you some

motivation and also proof that this methodology works so I had uh one student he actually just messaged me a

couple weeks before defc and I was super excited to see this um I didn't know him before but he said I took I took your

course and he had you know chatting with him he had never done any iot packing he took my suggestion he went and got a

cheap uh smart camera off Amazon and he actually was able to find three vulnerabilities in it got in touch with

a vendor and he's got three CVS coming so super excited for him about that uh and then this was another message this person didn't want me to put their name

up but he he took my course as well and then he bought a cheap router and he found a uh remote code execution

vulnerability in it and I just was chatting with him about how he could submit that to a CNA because the uh vendor didn't want to talk to him about

it but how he found a vulnerability so this chat is for everyone of course

if you're here I'm I'm glad you're here uh if you are if you're new to iot or you're iot curious as I say uh this talk

is specifically catered to people who are new or just curious about iot and it's going to assume you have limited or

no experience with iot or embedded systems so just a really quick agenda of

what we're in for today we'll start with some really quickly safety and and legal considerations we'll then talk about

what device you should actually pick if you're getting started on um so if you want to go home and buy something off

Amazon what you should look for if you're going to go dumpster diving for example um we'll then talk about how you can build out an affordable toolkit and

what stuff you should buy or what stuff you should avoid and how to not you know break the bank doing this then I'm going

to take a look at locating using and abusing Hardware interfaces we'll then talk about acquiring firmware and then

after that we get our hands on the firmware we'll talk about analyzing and reverse engineering it so just a really

quick staying out of trouble this is kind of like the Golden Rule of ethical hacking in my opinion only test devices that you're authorized to uh and then

this is just my personal suggestion since I am giving a talk about potentially how to go out and find uh

CVS and iot devices but I always recommend being ethical and following responsible disclosure if you do find

things uh unfortunately for a lot of iot devices they don't have bug Bounty programs but they do have responsible

disclosure so you can at least report it get some credit and get a cve that way or something so last one's up to you but

you know I would implore you to to go that route if you find something okay so I did want to just

give a little chat about staying safe because sometimes I give workshops or things like that and I teach people

about iot and Hardware hacking and they're a little bit nervous about opening up a device and working on the

hardware of it so the first thing I will say is iot hacking is in itself uh very

inherently safe so Hardware hacking on Commercial iot devices and that's really

if you just only follow one basic rule you'll be fine uh and that rule is that you should never work on anything high

voltage so when you open up the device you're working on it most of these devices are going to be like 12 volts 9

volts 3.3 volts 5 volts operating voltage all of those are for the most part safe to work on you probably won't

even feel it if you touch it the voltage from our walls and our house and stuff that stuff can really hurt you so just

stay away from that stuff just work inside your device you'll be fine uh never use any damaged or modified Power

Supplies because that's how we can accidentally introduce those higher voltages into the device damage our device ourselves uh and then this last

one is more about keeping your devices safe but when I give workshops I see people doing this all the time this is

the most common way to Brick or fry your device but if you have it open and you're working on it then that's not how

the manufacturer intended you to be using it and if you're plugging in Clips or wires or things like that if you have

it powered on it's easy to bridge something and do a short circuit and that's the easiest way that I see people

who are learning fry their device so it's just really good practice if you're not using it turn it off plug it

anything in you need then turn it on when you're done and if you need to uncp it you power it off then you work on it and it's easy to forget I'm always

walking around my workshops Waring people of that last thing I just want to give a really quick shout out to because

people have gotten seriously injured from this or hurt uh doing this you aren't really going to counter these in iot devices but if you take your

Hardware hacking skills that you learn from this to other things that have larger power supplies is watch out for large capacitors because these can

actually pack a punch as far as the amount of energy they store and also some people don't realize but when you

unplug these devices or capacitors from the wall they can hold their charge for quite a while so you may think you're

safe but they can zap you this is not common in pretty much all iot devices but I just say this cuz a lot of people

have this misconception if it's unplugged it's safe but if there's large capacitors that's not the

case okay so now that we've got all of the Preamble and everything out of the way we can get on to you know kind of my

methodology for how you can go home get a cheap consumer iot device and hack it so the first thing to do is actually to

pick the right target if you're learning so I always suggest the cheaper

the better when you're starting to learn and there's a couple reasons for this the first one is and this isn't always

the case but usually you get what you pay for in terms of security and also Hardware security so on cheaper devices

you generally won't run into limitations on the hardware where the debug ports are locked down or the firmware is

encrypted and then the second one which kind of goes with my second Point here is I never hack anything that I don't

mind uh bricking or destroying and if it's a cheap device then you're not going to be as concerned or upset if you

fry it um and you know I'll raise my hand and say I still you know fry or brick devices it happens I've been

Hardware hacking for a long time and it still happens uh and if you're a follower of Joe gr for example probably

one of the most famous Hardware hackers he gave a talk a few defc ago he literally he literally just talked about

all of the devices that he had bricked over the years so it happens to all of us um if you're looking for a specific

type of device my suggestion is to go with cheap routers or cheap smart cameras uh they're great to start on

they usually have vulnerabilities that you can find and also more importantly They al almost always run embedded Linux

uh which in my opinion is a much easier uh type of device to hack on when you're learning than something with a

microcontroller uh like a ESV 32 or stm32 that's going to be running at ARS those are a little bit more advanced or

harder when you're getting started and I will give another shout out to dumpster diving so on my on this picture here

this is one of many bins I have at my house that are just full of old devices and I just kind of put it out into the

universe like my friends and family know that I'm this dude that likes hacking weird electronic stuff so if they're

throwing away their router or camera then they ask me or I find them in like uh disposal bins or whatever I can't

resist so it's a great way to learn though because usually these devices work fine people are just they're obsolete or whatever but they don't have

to worry about bricking them or anything okay so once we've got a device hopefully it's a smart camera or a

router or something we've got to acquire a little bit of gear to go along with this

methodology so I've got a couple rules for that the first one is we don't want to break the bank when we're starting out you might not know if you want to do

it or not we don't want this to be a a limitation uh I also generally find that

gear for iot hacking follows the 8020 rule so if you're not familiar with this

with this rule it's kind of the idea that for uh any given input that uh 20%

of the inputs are responsible actually for 80% of the output and I find that to be true with iot

hacking tools you'll need to get a few of them and they'll do most of the heavy lifting uh and then you'll need to acquire the more specialized expensive

tools for specific tasks sure at this point everyone's seen a lot of the meme of this Turkish

shooter guy uh and I just wanted to demonstrate this I was kind of poking fun last week in like the iot and

Hardware hacking Community about how we all like to acquire gear and I'll be the first one to say like I'm addicted to buying gear I've got all the stuff in

the left hand side of this picture uh but really when you're starting out with cheaper devices you can probably get away with literally two things and spend

$10 okay so the first piece of equipment that you should get if you don't have one already is a digital multimeter this

is like the Swiss RB knife of electronics it can do things like measuring voltage current resistance uh

do continuity testing mostly we will use this for verifying voltage levels and

also we can actually use it to find a lot of common debug ports without special equipment we can actually you

know ID those and then do further uh investigation into those ports you can literally spend $5 on this this yellow

one on here that's $5 I got this off AliExpress I've used it in my workshops before I mean I wouldn't use it for like

commercial QA testing or anything but as far as learning iot hacking getting started it's not bad um I have 5 to $100

listed here I wouldn't recommend spending more than $100 but you can but your $5 one honestly it's not that

bad the second piece of equipment you'll need is a USB 2x adapter and by X I mean

the protocols that our iot devices are going to be talking at the hardware level uh so these are where those like

debug and test ports come into play the most common ones are uart SPI or so you

sometimes you refer to a spy i2c JTAG and swd the most common one you'll

actually see and what we're going to be focusing on is uart so you can just go and get this $2 one and that will work

for this methodology you get these off alley Express Amazon sometimes it's come like a pack of four for $10 you get them

250 um so if you just want to go the cheap route you just buy this $2 one you'll be fine um if you kind of want a

future proof and you actually want a a tool to to work into I always recommend the tiger board I really like um they're

board and they have good training that's free that goes along with how to use it uh and it's going to talk all of these common protocols actually so it'll do

uart for you and then when you know if you need to to jump up to something JTAG s swd or I2 i2c then you can use this as

well okay so the last this is the last thing that's going to be in our toolkit is some sort of flash programmer you can

get these in all varying different levels but um this is a cheap one for $10 and we will use these to mainly

extract the firmware off the device if we can't get it from other methods um so most of the cheap iot devices I I see

and why I'm suggesting these routers and cameras they all use the same like standard uh SPI flash chip eight pin so

you can use a flash programmer generic one like this to read it if you did get the tiger you don't even need to get one

of these you can just use the the Spy connection on that and honestly you might not even need this so in my mean

before you were seeing us we get the firmware from the vendor then you don't even need a flash programmer you can just download

it all right so we got all our stuff we picked the device we've got our gear we're ready to start hacking the first

thing we're going to take a look at is abusing uh debug ports and Hardware interfaces so for the most part iot and

embedded devices they don't have any keyboard or Mouse input they don't have a monitor they just kind of do something

uh and if they're not doing that thing right then when you're designing it and as a designer your debug and test

interfaces these are like your only link to that device to see what's going on what's going wrong what's happening

making sure things are going properly uh so what happens in R&D of the cheap devices a lot of times is they will use

these throughout the R&D design process we'll get to the end device will be ready to go and they don't want to do another revision of hardware and things

like that or maybe firmware uh so they'll just leave these on the board open like they were when they were testing uh in addition a lot of times

they're actually used in production devices for things like debugging uh doing logging QA testing and possibly

even flashing memory or things like that uh the most two common ones I see are uart and JTAG we're just going to be

focusing on uart because on the majority of cheap consumer iot devices that's the

most present one and I almost always see uart that you can use and abuse

so this talk is like the no BS no filler version of it so I'm not even going to really teach you about what the art

protocol is only the things that you need to know to hack it uh it stands for universal asynchronous receiver

transmitter that just basically means there's no clock and there's two lines one one for receiving and one for

transmitting on it's a very old and common protocol for electrical communication um it's a little bit more

complicated than this but this the the basics of it is it literally just talks binary with voltage so it sends plus 3.3

volts or 5 volts for a one uh Zer Volts for a zero and I got a little picture

here of a capture if you're curious but that's literally all you need to know about it for the as far as uh hacking it

on it so getting uh connection to a devices you are if you're doing like a pen test

or something that would be a finding but for the most part the manufacturers don't actually care specifically about

that however actually getting access to the uart will make it a lot easier for

us us to be able to find vulnerabilities like something that could be exploited from the web it's going to make us a lot

easier to find those and the reason for that is we can view the devices logging so that's probably the most um important

thing in embedded devices there's usually not a lot of storage and there'll maybe be almost no actual

writable storage that we have so there's no place to store logs so instead we're just going to dump that all out to

uart uh in addition if we are encountering embedded Linux then usually we can actually use the uart connection

to get a shell into the device we can do further enumeration that way sometimes we can access the bootloader which is

responsible for it actually brings up the device and if we can get into the bootloader we can do things like dump the firmware see environment variables

um and so yeah getting uart is a great thing especially for the logging you can see uh in the picture here I'm just

looking at some of the boot logs and there's actually quite a bit of uh detailed versioning information that we can see

already so once you uh start using you and this happens to me like when I see a board it's very very easy to start

picking them out like whenever I see a PCB now just uh subconsciously I'm like oh that's art I can see it um so I start

looking for them and once you start noticing a few characteristics you'll be able to ID them so generally for full

duplex uart so this means that you got two devices your iot device and then maybe your computer that has the art

adapter you're talking to uh they're both talking to each other that means there's going to be a transmit line

which you'll see abbreviated always as TX a receive line abbreviated as RX and a ground sometimes you'll see a VCC and

I'm just calling that out because if you see four pins for our hacking purposes you can just ignore the BCC we don't we

don't even need to use it so unfortunately they won't always make it as easy like in this example

here uh they've gone so nice as to label them for us and all the hardware hackers but they won't always make it this easy

uh sometimes you'll have test pads like the ones uh here on this black circle PCB this is a camera that I was hacking

and you'll notice there's only two pins together but seeing those two pins together and close to the processor I thought that they might be uart then I

just picked up a ground elsewhere and then we got another router here where they've got uh a connector here for art

and it's not labeled but you know as soon as you see those pins together like that it's a good indication that it's some sort of test

interface so this is where we're going to pull out our DMM and we can use like our $5 DMM to actually pick up uart so

what we're going to do is we're going to take advantage of the fact that uart is extremely chatty on boot up so if you've

ever booted up like a your Linux computer even or some windows ones and you see all the stuff coming scrolling

through the screen telling you all those boot log information uh well embedded Linux is the same and that's going to

happen on the uart as well and we can take advantage of that so what we can do is use our multimeter put it on the

volts DC setting and measure our the pins of Interest so if we think there might be a UR pin we'll just measure

that from that from that connector whatever it is is two ground uh and then after we're doing that we'll power on

the device so I always like to have a power bar in my workstation that has a button it makes a lot easier um and what

you're looking for is a fluctuating voltage after that boot up it'll usually be like a couple seconds after it take a

second for like the initial boot loader to load things up and then you'll start to see a bunch of voltage hopping up and

down you won't see it go like 0 to 3.3 volts or 0 to 5 volts because it's going

to be too fast for our multimeter to read that so instead what you'll see is more of an average voltage kind of

moving around a lot of times these devices operate at 3.3 volts so you'll see like 1.5 to 2.7 volts and you'll see

that moving up and down um so if you see that that's a really indication I should look further at this port it's probably

transmitting something um if you just power on the device and do this you probably won't see anything because it's

not going to be as chatty it'll maybe just send a couple messages and it'll be really hard to even see those blips of

voltage you got to do it right at startup okay so we we found this port we've identified it the next thing we're

going to do is we can just it's as easy as we can just plug it into our computer basically we use our uart to USB bridge

adapter plug that into our computer the only thing you need to keep in mind for it is um it's really easy to put like

names together so you want to put TX to TX but the way that it works is one device is TX goes to the other one's RX

and vice versa so you just need to cross those lines grounds go to ground ignore the VCC you're all good so just for

reference I got a little picture here if you're looking at the slides later but that's the pin out that you would use usually

take so unfortunately sometimes they won't make it that easy they won't put the header pin on there won't be through hole connectors so what do we do in that

scenario your best option is to solder so hopefully you're hanging out at the soldering skill station but uh if not

there's there's ways we can get around that so if you are lucky enough to have through hole connectors like we did I

showed in the one router the best way to do that is to actually attach some header pins to it uh and if you don't

have those there's lots of Clips clamps adapters and things like that where you can buy um more specific to your device

Google's your friend here and they're really not that expensive so just go out and take a look at your different options and like just to show you if you

don't want to do soldering here's two things that I've done in a pinch and showing in classes where you can get away with um generally with through hole

connectors it'll actually be like connectivity that goes through the actual pin so if you put a little

pressure on what you're putting through it so kind of lean to the left or right that'll be enough to get good contact

and I did it here with a twist tie um or that's some some sticky tack and obviously soldering is your best option

but I don't want that to be a barrier to you know hacking iot if you don't have a soldering iron or to solder so this can

be done in a pinch if you're running on a Linux host I mostly just included these commands

here for people that are going to be taking these slides afterwards but all we need to do to actually get a a shell

or connect to the device is we need to just check and see what uh the device ID is for our USB to Ard adapter so we can

do that with this command uh and you'll get the the device ID back it'll most likely be TTY usb0 but it could be 1 2 3

uh and then we can just launch a terminal emulator and use that to get a UR connection when you're starting out I

suggest using screen because it's the easiest one there's lots of other ones picocom minicom uh putty if you're on

windows they're all fine uh but screen in my opinion is the easiest one it requires very little setup uh the only

two arguments you need is that USB device ID that I showed before and then you'll notice the last thing here I've

got a number 115,200 that is the B rate or speed that the uart is communicating at uh and since

this is no BS no filler talk I'm not even going explain what B rate is on 99%

of iot devices I see it is 115,200 so you can just use that if it's not it's

probably 9600 and if it's not that you're probably doing something wrong um there is also a very common list on

Wikipedia you can look at of other um once but it's pretty much going to be 11

152000 Okay so if everything worked with your connection you got screen running your power on device uh you should start

to actually now see those boot logs that we saw with our multimeter actually start streaming through uh and do not

discount the importance of actually reading through those boot logs and seeing what they are telling you they're going to give you lots of versioning

information that could be enough to even find a vulnerability on its own seeing that it's using you know underlying uh

libraries or things like that that are outdated and someone's already done the leg work and found a vulnerability in those we'll also give you details in

this one for example near the bottom it's showing all the partition details about the flash uh eom that's on it and

that's going to make it a lot easier for us later to identify the different parts of the firmware after the bootloader goes

through and you know it's done streaming through the text you can hit enter and a lot of times on cheap iot devices that

can be enough to just get a shell they don't lock them down with a password or anything so then we'll be in a root shell uh generally in embedded Linux

everything just runs as root there's no like lease privileges or anything you'll just get a root shell um again like in

the manufacturers they're not as concerned about this as being a specific vulnerability so I wouldn't recommend uh reporting this or anything because they

already know about it they just don't necessarily care but we're going to abuse that to find something they do care about the majority of the routers

and smart cameras they're running embedded Linux so that's where this is going to make it easier to get that shell okay so I always mention this

because you know in cyber security I feel like we all want to get a shell everyone loves getting shells and sometimes that's like the end allll of

what we're doing if we're doing like web app or or you know other different types of network pen testing um but for us

actually connecting to the art it's more important for us to see the logging that's actually what we're more we're

more interested in or at least I am so if you don't get a shell that's okay if you're not able to get in um that's fine

so sometimes there'll be a password if there is there's ways around that we can maybe uh get the hash from the firmware

or Google it but even if you can't get a shell that's okay the way that art works is like you don't need to authenticate

or log in it's a very like low-level protocol it's just going to stream those logging bits out to you no matter what

you don't need to log in or anything like that you can still see the logging unless the device like syncs or tanks to

uart um which most don't so I got just got some pictures here showing some interesting things I

see in logs one of them here is just showing the location of uh RSA Keys as it's setting up drop Barrow it's common

SSH protocol and then the other two ones are interesting uh logging details about

when I was actually interacting with the device and showing what could potentially be command injection or one is just showing

how it sets up and saves the pre-shared keys and ssids for a router so if you are lucky enough to get

a shell I mean I was saying it's not as important but it is always nice to get one uh we'll be good hackers then and do

our enumeration so start poking around best places to actually start looking are the Etsy folders and the VAR folders

those are probably some of the places where you'll find like interesting configuration details and things like that some some really quick wins are

things I look for is there passwords hardcoded Keys is there end points that maybe they don't want to expose or that

we could um see that's reaching out into the back end and of course A lot of times you'll have like things like PS or

net stat so you can see what processes are running and what network connections are going out so that can give us a little bit of a lay of a land around the

device okay so at this point you know we've got our device we've got our equipment we use our equipment to find

our debug interface what's the next step that's going to be to get our hands on the firmware and in my opinion this is

where my favorite part starts and where we can start having some fun and find some vulnerabilities if you're not familiar

with what firmware is this essentially the software that is running on the device and we kind of call it firmware

and differentiate it from software and that it's kind of designed specifically for that device so that that device can

fulfill one function it's not really changing you're not going to like install any software or anything on your router or smart camera we just get that

one piece of firmware in embedded Linux that we're talking about today the firmware is

generally comprised of four main parts we've got the bootloader that's responsible for actually like bringing

up the device on boot up loading up the kernel we've then got the Linux kernel itself that's going to be one partition

uh We've then got the root file system so that's actually where all of the interesting stuff is that make the

device do what it's going to do all of the binaries scripts um configuration

documents all of that stuff is going to be in the roof file system we'll then possibly also have some sort of

partition where we can store a little bit of writable data so we'll generally want to hunt for this as well because

that's where you're going to find things like uh passwords that users configured or like the maybe pre-shared key for

their Wireless or all that kind of stuff uh so a lot of times you'll see that at the end of the flash memory the root

file system has the most goodies though by far so that's all we're going to focus on today uh you can find

vulnerabilities in the other places in the bootloader and kernel but when you're starting out we'll just look at the root file system and its contents

and that's honestly where you'll find the majority of vulnerabilities anyway so there's three main ways that I

usually get my hands on the firmware there are a few other ones that are more complicated but uh the easiest one is a

lot of uh cheap iot manufacturers they just put their firmware available on the

internet from the vendor to download uh the reason for this is that Unfortunately they don't put any type of

update mechanisms into device uh so they kind of pass that responsibility down

onto the end users if there is security patching or things like that to go and hey make sure you go to our website

check it every day uh download the firmware and then uh put it on the device yourself which I think unfortunately i' would say like 99% of

users don't do um but to fulfill that obligation they put the firmware on their website on the support page and

you can just Google and find it and I love that because it's super easy to get our hands on the firmware uh and if you do that then you can even do iot hacking

for free free you don't even need any gear you just download the firmware the second way is if you did

get a Art Shell I would say like 90% of the devices I see they have tftp on them

so that's trivial file transfer protocol this is there because it's actually uh baked into the functionality of a lot of

those update mechanisms so if you have like a web app or a browser or something and allows you to do a firmware update

through that uh in the back end it uses tftp but we can you know abuse that or borrow it to set up our own tftp server

and then we can just just bring back files of Interest or if we're patient enough we can just bring the whole root file system back to our device over that

uh then we don't even really need to worry about dumping the firmware uh and then the last one which sometimes you'll need to do is you'll just dump the

firmware off of the device so in these cheap commercial iot devices that I'm

suggesting getting starting on they almost always use a eight pin spy uh

flash chip and these always follow the same pinout and we can use our Flash ra

or our Flash Reader that I suggested getting or the tie guard to really do a really quick read of these and we don't

even need to usually take them off of the device you can just read them in device in circuit and the way to do that

is I generally recommend using flash ROMs free open source software that's great for interacting uh with flash

chips so again command here for reference if you're just wanting to follow along later but if you get a c341

a programmer which is that $10 one uh that I recommended from the start then you can just run this command after you

put the clip on and it's as easy as that there's also other test Clips you can do uh to use it but it it's pretty

straightforward it it lists the different pins that match the pins on the chip you can just Google standard

SPI 8 Pin Flash and you'll see all of the pins there's six of them that you need to use out of the eight pins uh

just a heads up so if you did get the tiger you can do this with the

tiger Okay so we've all this basically everything we've been doing up until

this point now has been to set us up for successful reverse engineering of the

internals of the device uh to figure out what's going on and to hopefully find

some vulnerabilities um so that's what we're going to be taking a look at now and so

one thing you can do too if you don't want to spend any money is you just can go and find the firmware uh for download

and then you can do the majority uh of these steps as well and then you haven't even spent a dollar or you could also

try and emulate the firmware as well it's not something we're going into today but I just want to give that a a call out like if you can't get your

hands on a device you don't want to spend any money you just kind of want to get started you can do it for free just get your firmware try and reverse

engineer it uh and emulation is your friend okay so the first thing we do

once we get our hands on the firmware is it's generally going to be in like a kind of like a blob format so generally

it's going to be in like a a bin file or a binary file or maybe a hex file possibly IMG but it's not going to be

probably readable for us at that point so we need to go ahead and actually unpack that firmware uh into the

different sections and and files that are actually in there that we'll be able to interact with better so the very

first thing we're going to do is cross our fingers that it's not encrypted um so again this is why I'm recommending

when you're starting out go for those cheaper devices because most likely they're not going to use uh encryption

for their firmware because it costs money both in uh software development and R&D but but also you're most likely

going to need to spend a little bit more uh on Hardware to actually rely on that to handle that decryption at the

startup if you do come across encrypted firmware and you're just getting started my suggestion would be just save that

device for later down the road um it's not like it can't be defeated there's lots of attacks and things like that

that we can do to try and uh defeat the encryption and find the keys when the obviously when it's booting up it's

going to need to actually do that decryption and we can possibly read the keys uh but it's a little bit more of an advanced topic so I'd save that for down

the road after you've done a few and go and find another device and see if you can make sure that it device is not

encrypted so how do we check if it's encrypted and also how do we get the contents of that we will use a utility

called binwalk so there's a bunch of tools to to do this uh and various ones and you can take a manual approach but

the easiest way and is to just go ahead and use binwalk uh if we pass it two

options the capital M and the E it will just recursively go through and anything it identifies that it can pick up uh as

a file type that it knows it will try and uncompress that or unzip it or whatever until it gets down to the

actual it knows the file types whether that's a binary file shared object XML uh

whatever and the E is telling us to extract it actually so if you just run binwalk without any commands it'll

actually just tell you what it sees and then if you pass in the E it'll go ahead and try and actually break those down so

awesome tool it does a lot of the leg work for us um alternatively we saw that we had those different partitions

already actually listed out for us in the boot log so you can use uh DD as well if you want a manual approach just

to carve it up and sometimes you have to but binwalk is your friend it most it works most of the

time okay so this is where the fun starts so now that we've got the firmware we're going to go and actually

uh focus on the root file system and see what we can find so some really lwh hanging fruit is just to look for the

configuration files and poke through those see if we can find anything that shouldn't be in there um so a lot of

times when I'm teaching iot hacking people are surprised to see but the most pop the best tools I think are just some

of the really easy basic Linux tools like fine strings and grep they go a long way um with iot hacking and we can

use find with the dash name argument and I like to just do like star. extension

so I'll do star. XML star. text star. Json and I'll just through that and read

through those documents a lot of times see XML and sometimes they have interesting details in there that's some lwh hanging fruits uh we can also use

strings so this is a tip that I I teach if you use strings with the dash F fun uh the- F tack on it it'll bring back

the file name that's attached to that string and then we can run strings over like a whole file system or a whole

group of files uh and if we and then we can pipe that into grep and look for things like password API key all of

those things sometimes I'll look for like Doom for for example or or various tlds just to see if we can find any

endpoints and that can just be an easy win as well using strings and piping it into grap it's one of my favorite tricks

when iot hacking is to to do that the next thing we'll take a look at

that is like pretty easy because same with the the readable files all of the scripts so a lot of times since it's bed

Linux it's going to be bash or sh scripts you don't need to decompile them you can just take a look at them read

through them a lot of times the developers will put really nice comments in there telling you what they're doing because they're being good developers

and putting comments and things like that it's funny I've seen like even things like people's emails or like you know make if you find a problem with

this email me at this email or things like that um but the one scripts that I always suggest and you should look at um

right when you're getting started with a device and looking at it are the RCs scripts so most iot devices use a tool

called um busy box which is a way to actually combine all of the binaries into one binary to shrink them down and

then they use their AIT process uh and the way that busy box works is it runs

all of the RCs scripts in Etsy init.d so after the bootload is finished and Linux

is done it hands off to the busy box init system and then it calls all of the scripts in there that start with RCS and

it does them in alpha numeric order so it'll go like RCS one two or if you have like sometimes you see like uh one and

it tells you what they're doing and these scripts are great because they're responsible for actually setting up the

device past Linux for what it actually does so if it's a camera or router then it's probably going to you know bring up

binaries or things like that to actually do what the device does or sometimes it'll even reach out to like a backend

infro or Cloud infra to let it know it's up or pass back information uh and again these are human readable like they're

just bash scripts so no decompiling no real reverse engineering uh and another tip too is if you're not familiar with

bash like honestly chat GPT is really great at um breaking down what bash scripts are so you can just copy and

paste these directly at the firmware into our friend chat gbt and it can help you out and tell you what's going on as

well um yeah I frequently don't really find specific vulnerabilities in here sometimes you'll find things that shouldn't be in there but most of the

reason is just to get a lay of the land and and it'll tell you about like what's going on what binaries are being executed things like

that okay so now we're at in my opinion the most fun part and kind of like everything even the other stuff before

that has been leading up to setting ourselves up to be successful at reverse engineering the binaries and libraries

that are on the device so this is where you're honestly most likely to find some sort of vulnerability uh that you're

going to report and one complicated or thing that I see people get stuck with on this is where do we actually start

it's quite possible there's dozens to hundreds to maybe a thousand different libraries and binaries on the device uh

it takes a lot of time to reverse engineer and understand these so which one do we pick uh and how do we start

so the easiest way to actually do this is to avoid a needle in a Hy stack situation is to go with like a forward

down approach and this is what I teach or the methodology I teach when people are starting and that is to start with

the custom binaries and libraries that are actually unique to the device so a lot of the libraries and binaries are

going to be Linux stuff um so if you're familiar with using Linux you might be able to just discount quite a few of

these um but if you're not or sometimes it could be hard to tell especially with libraries did you know are these open

Source Linux things that do Linux or C stuff or are these ones that the designers of this device have actually

created um so then we run into the problem is how do we know they're custom and after you start to do this for quite

a while you will start to pick out the names and stuff and go like oh yeah that's that's a custom one um but if we

don't then the thing that I suggest to do is to interact with a device and then follow that logging and Trace that

logging down to the underlying binaries uh and functions and this is in my opinion the easiest way when you're

starting to actually find vulnerabilities so here in this picture

I've got an example so this is a a common uh router here that uh that I like to hack on and I went to the web

browser of it so just like most routers it's got a web browser where you can go on do lots of stuff set the pre-shared

uh key set what type of uh if it's WPA2 WAP or whatever you know set all that

stuff it's got a bunch of utilities for some reason it's got a ping test thing you can make the router ping other stuff

um so in this example I'm just playing around with that cuz I kind of suspected that it might be you know doing bad

things when we try and ping stuff um and so I wanted to find the underlying binary or um function or Library that's

actually responsible for that so what I do is I just go and play with all the functionality if there's something that

you can do on the device to make it do something I do that and I don't specifically do that like trying

injections or anything I just when I'm starting out just use the device how it's supposed to be used um and I'll

take a look at the logging and a lot of times the logging will be very verbose in iot devices when you're interacting

with things and then we can actually Trace that logging back then to the underlying binaries or libraries uh so

in this device and actually see this in a decent amount of iot devices they were nice enough to even just put the the

function that's actually calling um that is actually being called when you try and run this ping test they put it in

square brackets that's their like logging um nomenclature or whatever so it was called util uncore ex act system

so when I saw this immediately and if you're familiar with like you know web pen testing or something like that immediately looked like it was making a

system call to me uh and then they put a bunch of details in like they actually give us how the um command is being

formatted so I didn't get to put the whole thing because I was running out out of room but if you can't see it it literally says oal start Ping command is

IP p-c and it gives the whole details and in that you can actually see the IP address that we put in um so it

definitely is kind of like giving us a hint that there's possible command inje or something we should look at deeper

there okay so now we have an idea that that function that _ exec system is of

interest to us it could be a potential injection Point um and and what we should do is you know on the past page

or like when we're doing that like I will interact with everything I can and take a note of where all the logging is happening um what binaries and functions

that logging is coming from we'll just go back to our good friend strings piping into GP one of my favorite tools

for iot hacking uh and we can GP on that function name so a lot of times in less

expensive iot devices again they're making it easier for us they don't strip uh binaries and things like that so the

function names will just end up compile in the compiled binaries and libraries uh so we can just pipe that into grep

and put the function name in so in this example here I did that for util exec system however what if they do strip it

well if we just go back one page here um you can see the print out here it kind of follows a format it says oal start

Ping command is and then gives the command um so that's a string that's actually in there too and they're

probably not going to OB you SK it it's not malware so we can also just pipe uh common uh strings that we see so in this

example I kind of thought I was using like a printa or Sprint or something like that so we looked for command is

and we get the same hit you can see here that actual uh string how it is in that binary is percent S command is percent s

so it's using that formatting um so even if they do strip the function names there's still ways to get around it and find those underlying binaries and

libraries okay so now that we've got our uh

function name we know that it's in that so if I just go back in this one for example we see the hit because we use DF

it's in this lib CMM doso so that is a custom library that the makers of this

router in this example wrote that has the majority of the functionality uh of that router baked into it we can pop

that into gedra and start decompiling it so one of the things that I find when

I'm teaching iot hacking or in my workshops is like this is the point where people usually get a little bit overwhelmed if they're not familiar with

um reverse engineering and it starts to look quite complicated because the output of gidra can be very uh verbose

when it decompiles it it is in my opinion a little bit more complex than just looking at regular code uh so it

can be a little like discouraging and I see some people are like okay I can't do this I'm intimidated by it but I have a

few tips that I think can make it a lot easier for you to understand and read the output in here and still find

vulnerabilities even if you don't understand what the heck is going on and most of it doesn't make sense um so the

very first thing I always say and is because people who are in cyber security and have had a little bit of an intro to

gedra or reverse engineering is it's usually looking at malware and this is not malware so with malware usually good

malware authors or majority of them are going to try and obus skate what they're doing make it confusing for reverse engineering they're not going to use

print statements if they have strings they're going to obus skate those strings so they're very hard to see uh instead for our iot devices we have

developers who are trying to be good helpful developers and write very clean readable codes so that it's easy for

someone else to pick up after them if someone's reading their code it's going to be testable debuggable doing all

those good things uh that developers do and also in iot devices we do a lot of

printing out to uart to tell what's going on so that we can actually do

almost debugging through print statements in a production device which is nice it makes it really easy for us

to then uh go and Trace those back so one of the first things I always suggest with that in mind is to take a

look at the print statements and let those guide you to what is going on um of course you can't always trust print

statements if you're a programmer you know that it's not the best to always trust comments or print statements but when you're getting started reverse

engineering I think it's okay just read the print statements uh the very first one that I have here that's in red it's

just actually that print statement that we saw in the logging so it helps us confirm that we're in the right spot uh

and then if you look down at line 32 it might be a little hard to read but essentially what it's saying there is it's just saying system Fork failed uh

and this we don't care about that it's not important to us but if you look at the um program flow and the if

statements well now you know what that program flow does it just checks if a system Fork failed because before that

it says you know if local 234 equals FFF f f FF well if I saw that I have no idea

what it was is it integral to the thing well if you look at the print statement it tells you exactly what it is you could just ignore that the second thing

you can do with print statements that makes your life a lot easier is a lot of times they'll be like print FS or Sprint

FS uh and if you're not familiar with how those work essentially we have a slot holder for uh a variable that we're

going to pass into that print statement and then the print statement basically tells you what that's what that variable

is so in this top example here we have the percent command is percent and then

we have two variables passed in that you know we wouldn't know what they were one's pram 1 and one's underscore _ s

well if we look and you know we just go back a couple to that print statement well the first one this is that identifier oore start Ping command so we

know maybe that's like some sort of identifier and then the second one though now we know of our interest well

that's the actual string that we manipulate that we can pass the IP address in and because of that um Sprint

F or that print F function well now we know that underscore uncore s variable we know what it is and that's just

through those print commands the next thing call out or that's kind of like the final thing that

we've been working towards is to just start getting used to seeing um unsafe things being done so the the easiest one

to actually find is system command so you can see that's in the second Square there we have a system command and if

you're not familiar with that when you're programming C essentially that's a way for you to just pass down to Linux

to say like hey I want you to run this like shell command um so it's essentially the same as if you know you're at the terminal and you type in

if you have a shell what whenever you pass it to system it's the same way so if you're not already thinking this like

this is an extremely dangerous thing to do in your programming uh if you're using user variables and especially if

you're not going to be sanitizing those variables um so in this one for example this _ EXA system function that they've

written to make it easier to do system calls it does no sanitization or checking however um in this example the

caller of that that actually initially takes in uh that IP address

well it does do the sanitization but if you look on this device for example there are about um 500 calls to this _

exec system and the person that wrote that function this _ exec system that knows okay I need to sanitize my inputs

further down the chain they might not be the same ones writing the code so you can actually see how it can um happen to

slip through where user supplied input gets into a system call so that's one of the easiest things when you're starting

out is to just go interact with device chase down the inputs that you do cuz

you know and see where do they end up in the code and if they end up in a system call then I really need to look into

this deeper and see if there's a way that I can do some sort of command injection so of course what's next after

we know this well we keep interacting with the device and tracing the logging um back to the binaries or libraries so

of course there's other ways to approach this you could just start with the library and look at all the system calls and go backwards but when you're getting

started I think it's a lot easier to understand and concept iiz and not get lost in gedra to try and start at the

source which is how we interact with it and we know that there's um like an injection point there and then see if

that actually filters down to something um so don't just use web browsers like a lot of iot apps they have a mobile or

iot devices they have mobile app so we can go use that mobile app like do everything in the mobile app do all the

setup um check all of that cuz it's going to be like a lot of times one of those lesser used places where there's

some obscure setting or something you can set do all of that and see what logging you can get and Trace that back

and see where it goes like one example I found where I was able to crash a device is it was a camera and um if you wanted

to pair it to your mobile app you put the QR code up to the camera and you could pair it to the mobile app and I

was never able to like get any um buffer overflow or anything but I was able to crash the camera by doing like a

malformed um QR code so just be creative if there's cloud like somewhere you can sign up in the cloud and then interact

with your device uh do that like usually there's a free 30 days or something and you know we're not actually pent testing

the cloud thing we don't want to be like trying to break that but just interact with it how you're supposed to and see

how that filters down into the device and then what we're looking for is when you're starting out there's two main

things I suggest to look for so the first one is what we already looked at does it end up in an unvalidated or

unsanitized system call um and like if you look at this router and go back and

look at the CVS for this one that I'm showing or lots of iot devices you'll see lots of command injections being

done because in cheap iot devices they want to save money they don't want to write their own functionality it's way

easier to just use the built-in stuff in Linux and just hand it off to a system call um so it's not like these don't

exist you can definitely find them um the second one that's probably a little bit more common but a little bit harder

to find uh and and abuse is if it gets your your input user input gets put into

an unsafe C function so there's a few examples of those are mem copies string copy string cat uh print F that next one

is supposed to be Sprint F get scan F so essentially what these are doing though is they're going to be copying your data

um into some sort of buffer and again memory is limited on iot devices so we're always trying and be kind of

Stingy um with our buffers and a lot of times if you're not un if you're not sanitizing or validating those inputs

then it can end up in a buffer where we can overflow it and um you know at the worst case buffer overflow or maybe just

crash the device and have some sort of denial of service um so I could give a whole another talk then about where to

go from that from here and how to actually then um abuse these or actually exploit buffer overflows but if you do

get this far and you find this and like you'll be able to maybe crash the device or get some seg faults or something uh

then send me a message or just go out and do some further research and uh there's a lot of great resources then

for how to identify these buffer overflows so that's where I'll end today I just want to wrap up with a thank you

thanks everyone for uh coming I hope you learn something I hope you go home and uh go buy a cheap iot device when you

get home hack it if you do let me know I love to hear when people hack it and uh if you want to copy of these slides stay

in touch with me link up resources anything uh you can reach me at andrew.com thanks everyone